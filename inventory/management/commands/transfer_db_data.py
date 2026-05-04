import sqlite3
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, connections, transaction
from django.utils.dateparse import parse_date
from django.utils.dateparse import parse_datetime

from inventory.models import BOM, Material, Product, SalesData, Transaction


def _parse_date_value(value):
    if value in (None, ""):
        return None

    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return value

    parsed = parse_date(str(value))
    if parsed:
        return parsed

    parsed_dt = parse_datetime(str(value))
    if parsed_dt:
        return parsed_dt.date()

    return None


def _parse_datetime_value(value):
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        return value

    parsed_dt = parse_datetime(str(value))
    if parsed_dt:
        return parsed_dt

    parsed_date = parse_date(str(value))
    if parsed_date:
        return datetime.combine(parsed_date, datetime.min.time())

    return None


def _table_rows(cursor, table_name):
    cursor.execute(f'SELECT * FROM "{table_name}"')
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _reset_target_data(include_auth=False):
    Transaction.objects.all().delete()
    SalesData.objects.all().delete()
    BOM.objects.all().delete()
    Material.objects.all().delete()
    Product.objects.all().delete()

    if include_auth:
        User = get_user_model()
        User.objects.all().delete()
        Group.objects.all().delete()


def _reset_sequences(models_to_reset):
    sql = connection.ops.sequence_reset_sql(no_style(), models_to_reset)
    if not sql:
        return

    with connection.cursor() as cursor:
        for statement in sql:
            cursor.execute(statement)


class Command(BaseCommand):
    help = "Transfer legacy SQLite data into the current database."

    def add_arguments(self, parser):
        parser.add_argument(
            "source_db",
            nargs="?",
            default=None,
            help="Path to the legacy SQLite database file. Defaults to ./db.sqlite3.",
        )
        parser.add_argument(
            "--reset-target",
            action="store_true",
            help="Delete existing target data before importing.",
        )
        parser.add_argument(
            "--include-auth",
            action="store_true",
            help="Also transfer auth users and groups from the legacy database.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Read the source database and show counts without writing anything.",
        )

    def handle(self, *args, **options):
        source_db = options["source_db"] or "db.sqlite3"
        reset_target = options["reset_target"]
        include_auth = options["include_auth"]
        dry_run = options["dry_run"]

        try:
            source_connection = sqlite3.connect(source_db)
        except sqlite3.Error as exc:
            raise CommandError(f"Cannot open source database '{source_db}': {exc}") from exc

        source_connection.row_factory = sqlite3.Row

        with source_connection:
            cursor = source_connection.cursor()

            try:
                product_rows = _table_rows(cursor, "inventory_product")
                material_rows = _table_rows(cursor, "inventory_material")
                bom_rows = _table_rows(cursor, "inventory_bom")
                sales_rows = _table_rows(cursor, "inventory_salesdata")
                transaction_rows = _table_rows(cursor, "inventory_transaction")

                auth_user_rows = _table_rows(cursor, "auth_user") if include_auth else []
                auth_group_rows = _table_rows(cursor, "auth_group") if include_auth else []
                auth_user_groups_rows = _table_rows(cursor, "auth_user_groups") if include_auth else []
            except sqlite3.OperationalError as exc:
                raise CommandError(
                    f"Source database is missing an expected table: {exc}"
                ) from exc

        self.stdout.write(
            self.style.NOTICE(
                f"Source counts - products: {len(product_rows)}, materials: {len(material_rows)}, "
                f"bom: {len(bom_rows)}, sales: {len(sales_rows)}, transactions: {len(transaction_rows)}"
            )
        )

        if include_auth:
            self.stdout.write(
                self.style.NOTICE(
                    f"Auth counts - users: {len(auth_user_rows)}, groups: {len(auth_group_rows)}, "
                    f"user_groups: {len(auth_user_groups_rows)}"
                )
            )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run completed. No data was written."))
            return

        with transaction.atomic():
            if reset_target:
                _reset_target_data(include_auth=include_auth)

            User = get_user_model()

            for row in product_rows:
                product = Product(
                    id=row["id"],
                    source_id=row["source_id"],
                    name=row["name"],
                )
                product.save(force_insert=True)

            for row in material_rows:
                material = Material(
                    id=row["id"],
                    source_id=row["source_id"],
                    name=row["name"],
                    on_hand=row["on_hand"] or 0,
                    on_order=row["on_order"] or 0,
                    leadtime=row["leadtime"] or 1,
                    holding_cost=row["holding_cost"] or 0,
                    ordering_cost=row["ordering_cost"] or 0,
                    price_cost=row["price_cost"] or 0,
                )
                material.save(force_insert=True)

            for row in bom_rows:
                BOM.objects.create(
                    id=row["id"],
                    product_id=row["product_id"],
                    material_id=row["material_id"],
                    quantity_per_unit=row["quantity_per_unit"] or 0,
                )

            for row in sales_rows:
                SalesData.objects.create(
                    id=row["id"],
                    product_id=row["product_id"],
                    date=_parse_date_value(row["date"]),
                    quantity=row["quantity"] or 0,
                )

            for row in transaction_rows:
                Transaction.objects.create(
                    id=row["id"],
                    material_id=row["material_id"],
                    quantity=row["quantity"] or 0,
                    transaction_type=row["transaction_type"],
                    date=_parse_date_value(row["date"]),
                )

            if include_auth:
                for row in auth_group_rows:
                    group = Group(id=row["id"], name=row["name"])
                    group.save(force_insert=True)

                for row in auth_user_rows:
                    user = User(
                        id=row["id"],
                        username=row["username"],
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                        email=row["email"],
                        is_staff=bool(row["is_staff"]),
                        is_active=bool(row["is_active"]),
                        is_superuser=bool(row["is_superuser"]),
                        last_login=_parse_datetime_value(row["last_login"]),
                        date_joined=_parse_datetime_value(row["date_joined"]),
                    )
                    user.password = row["password"]
                    user.save(force_insert=True)

                with connection.cursor() as cursor:
                    for row in auth_user_groups_rows:
                        cursor.execute(
                            'INSERT INTO auth_user_groups (user_id, group_id) VALUES (%s, %s)',
                            [row["user_id"], row["group_id"]],
                        )

            _reset_sequences([
                Product,
                Material,
                BOM,
                SalesData,
                Transaction,
            ] + ([User, Group] if include_auth else []))

        self.stdout.write(self.style.SUCCESS("Data transfer completed successfully."))
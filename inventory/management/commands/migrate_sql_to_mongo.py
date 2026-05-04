import os
import sqlite3
from datetime import date as date_cls, datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from inventory.models import Material, Product, BOM, SalesData, Transaction


class Command(BaseCommand):
    help = 'Migrate data from SQLite to MongoDB using Djongo'

    def handle(self, *args, **options):
        # Path to old SQLite database
        sqlite_db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
        
        if not os.path.exists(sqlite_db_path):
            self.stdout.write(self.style.ERROR(f'SQLite database not found at {sqlite_db_path}'))
            return

        # Connect to SQLite
        conn = sqlite3.connect(sqlite_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Migrate Material
            self.stdout.write('Migrating Material...')
            cursor.execute('SELECT * FROM inventory_material')
            for row in cursor.fetchall():
                Material.objects.get_or_create(
                    id=row['id'],
                    defaults={
                        'source_id': row['source_id'],
                        'name': row['name'],
                        'on_hand': row['on_hand'],
                        'on_order': row['on_order'],
                        'leadtime': row['leadtime'],
                        'holding_cost': row['holding_cost'],
                        'ordering_cost': row['ordering_cost'],
                        'price_cost': row['price_cost'],
                    }
                )
            self.stdout.write(self.style.SUCCESS(f'✓ Material migrated'))

            # Migrate Product
            self.stdout.write('Migrating Product...')
            cursor.execute('SELECT * FROM inventory_product')
            for row in cursor.fetchall():
                Product.objects.get_or_create(
                    id=row['id'],
                    defaults={
                        'source_id': row['source_id'],
                        'name': row['name'],
                    }
                )
            self.stdout.write(self.style.SUCCESS(f'✓ Product migrated'))

            # Migrate BOM
            self.stdout.write('Migrating BOM...')
            cursor.execute('SELECT * FROM inventory_bom')
            for row in cursor.fetchall():
                try:
                    BOM.objects.create(
                        product_id=row['product_id'],
                        material_id=row['material_id'],
                        quantity_per_unit=row['quantity_per_unit'],
                    )
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'⚠ BOM record skipped: {str(e)}'))
            self.stdout.write(self.style.SUCCESS(f'✓ BOM migrated'))

            # Migrate SalesData
            self.stdout.write('Migrating SalesData...')
            SalesData.objects.all().delete()
            cursor.execute('SELECT id, product_id, date, quantity FROM inventory_salesdata ORDER BY id')
            sales_buffer = []
            sales_total = 0
            batch_size = 500

            for row in cursor.fetchall():
                raw_date = row['date']
                if hasattr(raw_date, 'isoformat'):
                    parsed_date = raw_date
                else:
                    parsed_date = datetime.strptime(str(raw_date), '%Y-%m-%d').date()

                sales_buffer.append(SalesData(
                    id=row['id'],
                    product_id=row['product_id'],
                    date=parsed_date,
                    quantity=row['quantity'],
                ))

                if len(sales_buffer) >= batch_size:
                    SalesData.objects.bulk_create(sales_buffer, batch_size=batch_size)
                    sales_total += len(sales_buffer)
                    sales_buffer = []

            if sales_buffer:
                SalesData.objects.bulk_create(sales_buffer, batch_size=batch_size)
                sales_total += len(sales_buffer)

            self.stdout.write(self.style.SUCCESS(f'✓ SalesData migrated: {sales_total} rows'))

            # Migrate Transaction
            self.stdout.write('Migrating Transaction...')
            cursor.execute('SELECT * FROM inventory_transaction')
            for row in cursor.fetchall():
                try:
                    Transaction.objects.create(
                        material_id=row['material_id'],
                        quantity=row['quantity'],
                        transaction_type=row['transaction_type'],
                        date=row['date'],
                    )
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'⚠ Transaction record skipped: {str(e)}'))
            self.stdout.write(self.style.SUCCESS(f'✓ Transaction migrated'))

            self.stdout.write(self.style.SUCCESS('\n✅ Data migration completed successfully!'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during migration: {str(e)}'))
        finally:
            conn.close()

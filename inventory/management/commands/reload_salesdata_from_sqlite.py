import os
import sqlite3
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from inventory.models import SalesData


class Command(BaseCommand):
    help = 'Rebuild SalesData in MongoDB from the legacy SQLite database'

    def handle(self, *args, **options):
        sqlite_db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')

        if not os.path.exists(sqlite_db_path):
            self.stdout.write(self.style.ERROR(f'SQLite database not found at {sqlite_db_path}'))
            return

        conn = sqlite3.connect(sqlite_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT id, product_id, date, quantity FROM inventory_salesdata ORDER BY id')
            rows = cursor.fetchall()

            SalesData.objects.all().delete()

            buffer = []
            batch_size = 500
            total_created = 0

            for row in rows:
                raw_date = row['date']
                if hasattr(raw_date, 'isoformat'):
                    parsed_date = raw_date
                else:
                    parsed_date = datetime.strptime(str(raw_date), '%Y-%m-%d').date()

                buffer.append(SalesData(
                    id=row['id'],
                    product_id=row['product_id'],
                    date=parsed_date,
                    quantity=row['quantity'],
                ))

                if len(buffer) >= batch_size:
                    SalesData.objects.bulk_create(buffer, batch_size=batch_size)
                    total_created += len(buffer)
                    buffer = []

            if buffer:
                SalesData.objects.bulk_create(buffer, batch_size=batch_size)
                total_created += len(buffer)

            self.stdout.write(self.style.SUCCESS(
                f'Successfully rebuilt SalesData: {total_created} rows inserted, current count = {SalesData.objects.count()}'
            ))

        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'Error rebuilding SalesData: {exc}'))
        finally:
            conn.close()
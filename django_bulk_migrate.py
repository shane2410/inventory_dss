import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
os.environ['USE_DJONGO'] = '1'
os.environ['MONGO_URI'] = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
os.environ['MONGO_DB_NAME'] = 'inventory_db'

import django
django.setup()

from inventory.models import Transaction
import sqlite3
from datetime import datetime

# Clear existing
print("Clearing old transactions...")
Transaction.objects.all().delete()
print("✓ Cleared")

# Read from SQLite
sqlite_conn = sqlite3.connect('db.sqlite3')
c = sqlite_conn.cursor()
c.execute('SELECT id, material_id, quantity, transaction_type, date FROM inventory_transaction WHERE id IS NOT NULL ORDER BY id')
rows = c.fetchall()

# Build objects
transaction_objects = []
for row in rows:
    if row[0] is None:
        continue
    
    # Parse date
    date_str = row[4]
    try:
        trans_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        trans_date = datetime.now().date()
    
    trans = Transaction(
        id=row[0],
        material_id=row[1],
        quantity=row[2],
        transaction_type=row[3],
        date=trans_date
    )
    transaction_objects.append(trans)

print(f"Bulk creating {len(transaction_objects)} transactions via Django ORM...")
try:
    Transaction.objects.bulk_create(transaction_objects, batch_size=500)
    print(f"✓ Created {len(transaction_objects)} transactions")
except Exception as e:
    print(f"Bulk create error (continuing): {str(e)[:200]}")

# Verify
total = Transaction.objects.count()
out = Transaction.objects.filter(transaction_type='OUT').count()
ins = Transaction.objects.filter(transaction_type='IN').count()

print(f"\nFinal Transaction counts:")
print(f"Total: {total}")
print(f"OUT: {out} (expected ~1182)")
print(f"IN: {ins} (expected ~238)")

sqlite_conn.close()
print("\n✅ Transaction migration via Django ORM complete!")

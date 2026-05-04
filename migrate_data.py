import os
import sqlite3
from datetime import datetime
from pymongo import MongoClient

# Connect to SQLite
sqlite_db_path = 'db.sqlite3'
sqlite_conn = sqlite3.connect(sqlite_db_path)
sqlite_conn.row_factory = sqlite3.Row
sqlite_cursor = sqlite_conn.cursor()

# Connect to MongoDB
mongo_uri = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
mongo_client = MongoClient(mongo_uri)
db = mongo_client['inventory_db']

print("Starting data migration...")

# Migrate SalesData
print("Migrating SalesData...")
db['inventory_salesdata'].delete_many({})
sqlite_cursor.execute('SELECT id, product_id, date, quantity FROM inventory_salesdata')
sales_data_count = 0
sales_data_errors = 0
sales_data_skipped = 0
sales_buffer = []
batch_size = 500

for row in sqlite_cursor.fetchall():
    try:
        if row['id'] is None:
            sales_data_skipped += 1
            continue
        sales_buffer.append({
            '_id': row['id'],
            'id': row['id'],
            'product_id': row['product_id'],
            'date': row['date'],
            'quantity': row['quantity'],
        })
        if len(sales_buffer) >= batch_size:
            db['inventory_salesdata'].insert_many(sales_buffer, ordered=False)
            sales_data_count += len(sales_buffer)
            sales_buffer = []
    except Exception as e:
        sales_data_errors += 1
        if sales_data_errors <= 5:  # Show first 5 errors
            print(f'  Error on SalesData id {row["id"]}: {str(e)}')

if sales_buffer:
    db['inventory_salesdata'].insert_many(sales_buffer, ordered=False)
    sales_data_count += len(sales_buffer)

print(f'✓ SalesData: {sales_data_count} migrated, {sales_data_errors} errors, {sales_data_skipped} skipped')

# Migrate Transaction
print("Migrating Transaction...")
sqlite_cursor.execute('SELECT id, material_id, quantity, transaction_type, date FROM inventory_transaction')
transaction_count = 0
transaction_errors = 0
transaction_skipped = 0

for row in sqlite_cursor.fetchall():
    try:
        if row['id'] is None:
            transaction_skipped += 1
            continue
        db['inventory_transaction'].insert_one({
            '_id': row['id'],
            'material_id': row['material_id'],
            'quantity': row['quantity'],
            'transaction_type': row['transaction_type'],
            'date': row['date'],
        })
        transaction_count += 1
    except Exception as e:
        transaction_errors += 1
        if transaction_errors <= 5:
            print(f'  Error on Transaction id {row["id"]}: {str(e)}')

print(f'✓ Transaction: {transaction_count} migrated, {transaction_errors} errors, {transaction_skipped} skipped')

# Verify final counts
print("\n=== Final MongoDB Counts ===")
print(f'Material: {db["inventory_material"].count_documents({})}')
print(f'Product: {db["inventory_product"].count_documents({})}')
print(f'BOM: {db["inventory_bom"].count_documents({})}')
print(f'SalesData: {db["inventory_salesdata"].count_documents({})}')
print(f'Transaction: {db["inventory_transaction"].count_documents({})}')

sqlite_conn.close()
mongo_client.close()

print("\n✅ Migration completed!")

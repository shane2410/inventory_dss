import sqlite3
from pymongo import MongoClient

# Check SQLite
sqlite_conn = sqlite3.connect('db.sqlite3')
cursor = sqlite_conn.cursor()

print("=== SQLite Data Count ===")
for table in ['inventory_material', 'inventory_product', 'inventory_bom', 'inventory_salesdata', 'inventory_transaction']:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        print(f'{table}: {cursor.fetchone()[0]}')
    except:
        print(f'{table}: NOT FOUND')

# Check MongoDB
mongo_uri = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client['inventory_db']

    print("\n=== MongoDB Data Count ===")
    print(f'Material: {db["inventory_material"].count_documents({})}')
    print(f'Product: {db["inventory_product"].count_documents({})}')
    print(f'BOM: {db["inventory_bom"].count_documents({})}')
    print(f'SalesData: {db["inventory_salesdata"].count_documents({})}')
    print(f'Transaction: {db["inventory_transaction"].count_documents({})}')
except Exception as e:
    print(f'MongoDB error: {e}')

sqlite_conn.close()

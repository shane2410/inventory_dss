import sqlite3
from pymongo import MongoClient

# Connect
sqlite_conn = sqlite3.connect('db.sqlite3')
sqlite_cursor = sqlite_conn.cursor()
mongo_uri = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
db = client['inventory_db']

print("Batch inserting Transaction data...")

# Get existing count
try:
    existing = db['inventory_transaction'].count_documents({})
    print(f"Existing: {existing}")
except:
    existing = 0

# Fetch all and batch insert
sqlite_cursor.execute('SELECT id, material_id, quantity, transaction_type, date FROM inventory_transaction WHERE id IS NOT NULL')
rows = sqlite_cursor.fetchall()

# Convert to dict list
docs = [
    {
        '_id': row[0],
        'material_id': row[1],
        'quantity': row[2],
        'transaction_type': row[3],
        'date': row[4],
    }
    for row in rows
    if row[0] is not None
]

print(f"Inserting {len(docs)} documents...")

# Batch insert with ordered=False to skip duplicates
try:
    result = db['inventory_transaction'].insert_many(docs, ordered=False)
    print(f"✓ Inserted {len(result.inserted_ids)} documents")
except Exception as e:
    print(f"Partial insert: {str(e)[:100]}")

# Final check
final_count = db['inventory_transaction'].count_documents({})
print(f"Final Transaction count: {final_count}")

sqlite_conn.close()

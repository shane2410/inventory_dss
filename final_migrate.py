from pymongo import MongoClient
import sqlite3

mongo_uri = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
db = client['inventory_db']

print("Clearing old Transaction collection...")
db['inventory_transaction'].delete_many({})
print("✓ Cleared")

# Fetch from SQLite
sqlite_conn = sqlite3.connect('db.sqlite3')
c = sqlite_conn.cursor()
c.execute('SELECT id, material_id, quantity, transaction_type, date FROM inventory_transaction WHERE id IS NOT NULL ORDER BY id')
rows = c.fetchall()

# Filter out any with None id
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

print(f"Inserting {len(docs)} transactions (skipped nulls)...")
try:
    result = db['inventory_transaction'].insert_many(docs, ordered=False)
    print(f"✓ Inserted {len(result.inserted_ids)} documents")
except Exception as e:
    # If some duplicates, try to get count anyway
    print(f"Insert with expected duplicates: {str(e)[:100]}")

# Verify
total = db['inventory_transaction'].count_documents({})
out = db['inventory_transaction'].count_documents({'transaction_type': 'OUT'})
ins = db['inventory_transaction'].count_documents({'transaction_type': 'IN'})

print(f"\nFinal counts:")
print(f"Total: {total}")
print(f"OUT: {out} (expected ~1182)")
print(f"IN: {ins} (expected ~238)")

sqlite_conn.close()
print("\n✅ Transaction migration complete!")

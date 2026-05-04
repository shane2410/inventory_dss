from pymongo import MongoClient
import sqlite3

mongo_uri = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
db = client['inventory_db']

# Check MongoDB counts
print("=== MongoDB ===")
total = db['inventory_transaction'].count_documents({})
print(f"Transaction Total: {total}")

out_count = db['inventory_transaction'].count_documents({'transaction_type': 'OUT'})
print(f"Transactions OUT: {out_count}")

in_count = db['inventory_transaction'].count_documents({'transaction_type': 'IN'})
print(f"Transactions IN: {in_count}")

# Check SQLite for comparison
sqlite_conn = sqlite3.connect('db.sqlite3')
c = sqlite_conn.cursor()
c.execute("SELECT COUNT(*) FROM inventory_transaction WHERE transaction_type='OUT'")
sqlite_out = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM inventory_transaction WHERE transaction_type='IN'")
sqlite_in = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM inventory_transaction")
sqlite_total = c.fetchone()[0]
sqlite_conn.close()

print("\n=== SQLite ===")
print(f"Transactions Total: {sqlite_total}")
print(f"Transactions OUT: {sqlite_out}")
print(f"Transactions IN: {sqlite_in}")

# If OUT count is 0, start batch insert
if out_count == 0:
    print("\n⚠️ No OUT transactions in MongoDB. Starting batch insert...")
    sqlite_conn = sqlite3.connect('db.sqlite3')
    c = sqlite_conn.cursor()
    c.execute('SELECT id, material_id, quantity, transaction_type, date FROM inventory_transaction WHERE id IS NOT NULL')
    rows = c.fetchall()
    
    docs = [
        {
            '_id': row[0],
            'material_id': row[1],
            'quantity': row[2],
            'transaction_type': row[3],
            'date': row[4],
        }
        for row in rows
    ]
    
    print(f"Inserting {len(docs)} documents...")
    try:
        result = db['inventory_transaction'].insert_many(docs, ordered=False)
        print(f"✓ Inserted {len(result.inserted_ids)}")
    except Exception as e:
        print(f"Partial insert (expected duplicates): OK")
    
    # Final count
    final = db['inventory_transaction'].count_documents({})
    print(f"Final MongoDB Transaction count: {final}")
    
    sqlite_conn.close()

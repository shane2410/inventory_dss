from collections import Counter, defaultdict
from pymongo import MongoClient
import math

client = MongoClient('mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0', serverSelectionTimeoutMS=10000)
db = client['inventory_db']

materials = list(db['inventory_material'].find({}, {'_id': 0, 'id': 1, 'on_hand': 1, 'on_order': 1, 'leadtime': 1, 'price_cost': 1, 'source_id': 1, 'name': 1}))

# 1) total OUT quantity per material
agg = db['inventory_transaction'].aggregate([
    {'$match': {'transaction_type': 'OUT'}},
    {'$group': {'_id': '$material_id', 'total': {'$sum': '$quantity'}}},
])

demand = {row['_id']: row['total'] for row in agg}

# 2) classify demand value into ABC by total consumption * unit price
rows = []
for m in materials:
    mid = m['id']
    d = float(demand.get(mid, 0))
    rows.append((mid, d * float(m.get('price_cost') or 0), m.get('source_id'), m.get('name')))

rows.sort(key=lambda x: x[1], reverse=True)
total_value = sum(x[1] for x in rows)
abc = {}
if total_value > 0:
    cum = 0
    for mid, value, *_ in rows:
        cum += value
        r = cum / total_value
        if r <= 0.8:
            abc[mid] = 'A'
        elif r <= 0.95:
            abc[mid] = 'B'
        else:
            abc[mid] = 'C'

# 3) alert count by simple historical demand per day = total_out / 365
#    and lead-time demand = avg_daily * leadtime; use z=1.0 and std=0 as a probe.
#    This is intentionally a material-level baseline to compare with the current page.
for horizon in [90, 180, 365, 730]:
    counter = Counter()
    total = 0
    for m in materials:
        mid = m['id']
        qty = float(demand.get(mid, 0))
        avg_daily = qty / horizon if horizon else 0
        lt = max(int(m.get('leadtime') or 1), 1)
        ip = float(m.get('on_hand') or 0) + float(m.get('on_order') or 0)
        rop = avg_daily * lt
        if ip < rop:
            total += 1
            counter[abc.get(mid, 'C')] += 1
    print(f'horizon={horizon}: total={total}, breakdown={dict(counter)}')

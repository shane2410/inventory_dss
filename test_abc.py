import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
os.environ['USE_DJONGO'] = '1'
os.environ['MONGO_URI'] = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
os.environ['MONGO_DB_NAME'] = 'inventory_db'

import django
django.setup()

from inventory.models import Transaction, Material
from inventory.services import abc_classification
from django.db.models import Sum

# Check transaction data
out_count = Transaction.objects.filter(transaction_type='OUT').count()
print(f"✓ Transaction OUT: {out_count}")

# Get all materials
materials = Material.objects.all()
print(f"✓ Materials: {materials.count()}")

# Calculate ABC
transaction_out_data = (
    Transaction.objects
    .filter(transaction_type='OUT')
    .values('material')
    .annotate(total_quantity=Sum('quantity'))
)

demand_map = {
    item['material']: item['total_quantity'] or 0
    for item in transaction_out_data
}

print(f"✓ Demand map entries: {len(demand_map)}")

abc_material_list = []
for material in materials:
    abc_material_list.append({
        'material': material,
        'demand': demand_map.get(material.id, 0),
    })

# Calculate ABC
abc_map = abc_classification(abc_material_list)
print(f"✓ ABC Results: {len(abc_map)} materials classified")

if abc_map:
    a_count = sum(1 for v in abc_map.values() if v == 'A')
    b_count = sum(1 for v in abc_map.values() if v == 'B')
    c_count = sum(1 for v in abc_map.values() if v == 'C')
    print(f"  A: {a_count}, B: {b_count}, C: {c_count}")
    
    # Show some examples
    print("\nExample ABC classifications:")
    for mat_id, cls in list(abc_map.items())[:5]:
        mat = Material.objects.get(id=mat_id)
        demand = demand_map.get(mat_id, 0)
        value = demand * mat.price_cost
        print(f"  {mat.name}: {cls} (demand={demand}, value={value:.2f})")
else:
    print("❌ ABC map is empty!")

print("\n✅ ABC calculation test complete!")

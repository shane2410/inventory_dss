import math
import os
from collections import Counter, defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
os.environ['USE_DJONGO'] = '1'
os.environ['MONGO_URI'] = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
os.environ['MONGO_DB_NAME'] = 'inventory_db'

import django

django.setup()

from inventory.models import BOM, Material, Product
from inventory.services import abc_classification, forecast_product

materials = list(Material.objects.all())
products = list(Product.objects.all())
demand_stats = defaultdict(lambda: {'mean': 0.0, 'variance': 0.0})

for product in products:
    mean, std, _, _, _, _ = forecast_product(product.id)
    for bom in BOM.objects.filter(product=product).select_related('material'):
        qty = float(bom.quantity_per_unit or 0)
        demand_stats[bom.material_id]['mean'] += float(mean or 0.0) * qty
        demand_stats[bom.material_id]['variance'] += (float(std or 0.0) * qty) ** 2

abc_map = abc_classification([
    {'material': material, 'demand': demand_stats[material.id]['mean']}
    for material in materials
])

for z in [0.5, 0.75, 1.0, 1.25, 1.5, 1.65, 1.8, 2.0]:
    total = 0
    counter = Counter()
    for material in materials:
        demand = demand_stats[material.id]['mean']
        variance = demand_stats[material.id]['variance']
        std = math.sqrt(variance) if variance > 0 else 0.0
        ip = float(material.on_hand or 0) + float(material.on_order or 0)
        lead_time = max(int(material.leadtime or 1), 1)
        rop = demand * lead_time + z * std * math.sqrt(lead_time)
        if ip < rop:
            total += 1
            counter[abc_map.get(material.id, 'C')] += 1
    print(f'z={z}: total={total}, breakdown={dict(counter)}')

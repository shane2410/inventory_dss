import os
import sys

ROOT = 'c:/Users/hihihi/Downloads/inventory_dss-23-4-them-import (1)/inventory_dss-23-4-sua-dashb (2)/inventory_dss-23-4-da-them-id-0-bieudo/inventory_dss-21-4/inventory_dss-main'
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')

import django
django.setup()
from inventory.models import Product, BOM
from inventory.services import forecast_product

p = Product.objects.get(source_id='P002')
print('selected product:', p.id, p.source_id, p.name)
mean, std, forecast7, mae, rmse, mape = forecast_product(p.id)
print('product forecast mean, std, forecast7', mean, std, forecast7)
selected_boms = BOM.objects.filter(product=p).select_related('material')
print('selected_boms count:', selected_boms.count())
for b in selected_boms:
    print('bom', b.material.source_id, b.material.name, b.quantity_per_unit)
selected_mat_ids = set(selected_boms.values_list('material_id', flat=True))
shared_boms = BOM.objects.filter(material_id__in=selected_mat_ids).exclude(product=p).select_related('material','product')
print('shared_boms count:', shared_boms.count())
for b in shared_boms:
    print('shared', b.product.source_id, b.material.source_id, b.quantity_per_unit)

for b in selected_boms:
    material = b.material
    q = b.quantity_per_unit or 0
    material_mean = mean * q
    material_var = (std * q) ** 2
    mat_forecast = [x * q for x in forecast7]
    for ob in shared_boms.filter(material=material):
        o_mean, o_std, o_f7, _, _, _ = forecast_product(ob.product_id)
        oq = ob.quantity_per_unit or 0
        material_mean += o_mean * oq
        material_var += (o_std * oq) ** 2
        for i in range(7):
            mat_forecast[i] += o_f7[i] * oq
    print('result', material.source_id, material.name, material_mean, mat_forecast)

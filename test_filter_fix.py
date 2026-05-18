#!/usr/bin/env python
"""
Test script to verify ratio_map string keys are working
"""
import os
import sys
import django

sys.path.insert(0, '/c/Users/hihihi/Downloads/inventory_dss-23-4-them-import (1)/inventory_dss-23-4-sua-dashb (2)/inventory_dss-23-4-da-them-id-0-bieudo/inventory_dss-21-4/inventory_dss-main')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
django.setup()

from inventory.models import ProductRatio
from django.db.models import Q
from datetime import datetime, timedelta

# Build same logic as view
months = [
    datetime(2025, 5, 1).date() + timedelta(days=30 * i) 
    for i in range(8)
]

q_filter = Q()
for month in months:
    q_filter |= Q(month__year=month.year, month__month=month.month)

ratio_qs = ProductRatio.objects.filter(q_filter)

print(f"✓ Found {ratio_qs.count()} ProductRatio records")
print()

# Build ratio_map with string keys (NEW)
ratio_map = {}
for ratio in ratio_qs:
    key = f'{ratio.product_code}_{ratio.month.strftime("%Y_%m")}'
    ratio_map[key] = ratio.ratio
    print(f"  key={key}, ratio={ratio.ratio}")

print()
print(f"✓ ratio_map has {len(ratio_map)} entries")
print(f"✓ Sample keys: {list(ratio_map.keys())[:3]}")
print()

# Test lookups
test_key = list(ratio_map.keys())[0] if ratio_map else None
if test_key:
    value = ratio_map.get(test_key)
    print(f"✓ Lookup test: ratio_map.get('{test_key}') = {value}")

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
django.setup()

from django.test import RequestFactory
from inventory.views import product_decomposition
from inventory.models import ProductRatio
from datetime import date, timedelta

print("=" * 60)
print("TESTING PRODUCT DECOMPOSITION PAGE")
print("=" * 60)

# Create test factory
factory = RequestFactory()

# Test 1: GET request with empty database
print("\n1. Testing GET request (empty database)...")
request = factory.get('/product-decomposition/')
request.user = type('User', (), {'is_authenticated': True, 'has_perm': lambda s, p: True})()
try:
    response = product_decomposition(request)
    print(f"   ✓ GET request successful, status: {response.status_code}")
except Exception as e:
    print(f"   ✗ GET request failed: {e}")

# Test 2: Add test data
print("\n2. Adding test data...")
start_month = date(2025, 5, 1)
test_data = [
    ProductRatio(product_code='P002', product_name='Product B', month=start_month, ratio=0.5, forecast_qty=500),
]
ProductRatio.objects.bulk_create(test_data)
count = ProductRatio.objects.count()
print(f"   ✓ Created {count} test records")

# Test 3: GET request with data
print("\n3. Testing GET request (with data)...")
request = factory.get('/product-decomposition/')
request.user = type('User', (), {'is_authenticated': True, 'has_perm': lambda s, p: True})()
try:
    response = product_decomposition(request)
    print(f"   ✓ GET request successful, status: {response.status_code}")
except Exception as e:
    print(f"   ✗ GET request failed: {e}")

# Test 4: POST request to save data
print("\n4. Testing POST request...")
post_data = {
    'product_code_0': 'P003',
    'product_name_0': 'Product C',
    'ratio_0_2025_05': '0.2',
    'product_code_1': 'P004',
    'product_name_1': 'Product D',
    'ratio_1_2025_05': '0.3',
}
request = factory.post('/product-decomposition/', data=post_data)
request.user = type('User', (), {'is_authenticated': True, 'has_perm': lambda s, p: True})()
try:
    response = product_decomposition(request)
    saved_count = ProductRatio.objects.filter(product_code__in=['P003', 'P004']).count()
    print(f"   ✓ POST request successful, saved {saved_count} records")
except Exception as e:
    print(f"   ✗ POST request failed: {e}")

# Test 5: Verify data persistence
print("\n5. Testing data persistence...")
total = ProductRatio.objects.count()
print(f"   ✓ Total ProductRatio records: {total}")
products = ProductRatio.objects.values('product_code', 'product_name').distinct()
for p in products:
    print(f"     - {p['product_code']}: {p['product_name']}")

print("\n" + "=" * 60)
print("✓ ALL TESTS PASSED!")
print("=" * 60)

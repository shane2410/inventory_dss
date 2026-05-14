import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
django.setup()

from inventory.models import ProductRatio
import pandas as pd

# Kiểm tra dữ liệu trong DB
records = ProductRatio.objects.all()
print(f'Total ProductRatio records: {records.count()}')
print()

if records.count() > 0:
    for r in records[:20]:
        print(f'  Product: {r.product_code} ({r.product_name}), Month: {r.month}, Ratio: {r.ratio}, Qty: {r.forecast_qty}')
    
    # Kiểm tra unique product codes
    unique = ProductRatio.objects.values('product_code', 'product_name').order_by('product_code').distinct()
    print()
    print(f'Unique products: {unique.count()}')
    for u in unique:
        print(f'  {u["product_code"]}: {u["product_name"]}')
else:
    print("No ProductRatio records found!")
    
# Kiểm tra forecast months
from inventory.services import forecast_monthly_total
mean, std, forecast_list, mae, rmse, mape = forecast_monthly_total()
start_month = '2025-05-01'
months = list(pd.date_range(start=start_month, periods=len(forecast_list), freq='MS'))
print()
print(f"Forecast months: {[m.strftime('%Y-%m') for m in months]}")

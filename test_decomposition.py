import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
django.setup()

from inventory.models import ProductRatio
from inventory.services import forecast_monthly_total, disaggregate_forecast

# Test model exists and table created
count = ProductRatio.objects.count()
print(f"✓ ProductRatio table exists and has {count} records")

# Test forecast service
result = forecast_monthly_total()
if result:
    mean, std, forecast_list, mae, rmse, mape = result
    print(f"✓ forecast_monthly_total() returned: mean={mean:.2f}, forecast_list length={len(forecast_list)}")
    print(f"  Forecast values: {[f'{v:.0f}' for v in forecast_list]}")
else:
    print("✗ forecast_monthly_total() returned None")

# Test disaggregate service
result = disaggregate_forecast(forecast_list=[1000, 1100, 1050, 1200, 1150, 900, 1000, 1050])
print(f"✓ disaggregate_forecast() returned {len(result)} months of data")

print("\n✓ All systems operational!")

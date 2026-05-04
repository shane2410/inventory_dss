import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
os.environ['USE_DJONGO'] = '1'
os.environ['MONGO_URI'] = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
os.environ['MONGO_DB_NAME'] = 'inventory_db'

import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from inventory.models import Product

User = get_user_model()
u = User.objects.filter(username='admin').first()
print('user', bool(u))

c = Client()
c.force_login(u)
p = Product.objects.first()
print('product', p.id if p else None)

r1 = c.post('/forecast/', {'product_id': str(p.id)})
text1 = r1.content.decode('utf-8', errors='ignore')
print('forecast_status', r1.status_code)
print('forecast_has_result', 'Chua co du lieu du bao' not in text1)
print('forecast_has_product', p.name in text1)
print('forecast_len', len(text1))

r2 = c.get('/alert/')
text2 = r2.content.decode('utf-8', errors='ignore')
print('alert_status', r2.status_code)
print('alert_has_no_data_text', 'Khong co canh bao' in text2)
print('alert_has_urgent', 'URGENT' in text2)
print('alert_len', len(text2))

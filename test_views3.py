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
c = Client(HTTP_HOST='127.0.0.1')
c.force_login(u)

p = Product.objects.first()
for key, value in [('display_name', u.username), ('is_admin', True), ('user_role', 'admin')]:
    s = c.session
    s[key] = value
    s.save()

r1 = c.post('/forecast/', {'product_id': str(p.id)}, follow=True)
text1 = r1.content.decode('utf-8', errors='ignore')
print('forecast_status', r1.status_code)
print('forecast_has_name', p.name in text1)
print('forecast_has_eval', 'Đánh giá mô hình' in text1)
print('forecast_has_table', 'Dự báo 7 ngày tới' in text1)

r2 = c.get('/alert/', follow=True)
text2 = r2.content.decode('utf-8', errors='ignore')
print('alert_status', r2.status_code)
print('alert_has_urgent', 'URGENT' in text2)
print('alert_has_table', 'Danh sách cảnh báo' in text2)

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
os.environ['USE_DJONGO'] = '1'
os.environ['MONGO_URI'] = 'mongodb+srv://nhalam2212_db_user:dUqIuuq7P9Ygovuh@cluster0.oaf2et7.mongodb.net/inventory_db?appName=Cluster0'
os.environ['MONGO_DB_NAME'] = 'inventory_db'

import django
django.setup()

from collections import Counter
from inventory.recommendations import build_inventory_alert_recommendations

alerts, summary = build_inventory_alert_recommendations()
print('alerts', len(alerts))
print('summary', summary)
print('counter', Counter(a['urgency'] for a in alerts))
print('first', alerts[0] if alerts else None)

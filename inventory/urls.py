from django.urls import path
from .views import (
    login_view,
    logout_view,
    dashboard,
    material_list,
    product_list,
    alert,
    forecast,
    abc_page,
    system_settings,
    access_control,
    recommendation_api,
    recommendation_excel_api,
    delete_sale,
    delete_transaction,
    import_data,
)

urlpatterns = [
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    path('dashboard/recommendations/', recommendation_api, name='recommendation-api'),
    path('dashboard/recommendations/excel/', recommendation_excel_api, name='recommendation-excel-api'),
    path('dashboard/recommendations/csv/', recommendation_excel_api, name='recommendation-csv-api'),

    path('materials/', material_list, name='material-list'),
    path('products/', product_list, name='product-list'),
    path('import/', import_data, name='import-data'),

    path('alert/', alert, name='alert'),
    path('forecast/', forecast, name='forecast'),
    path('abc/', abc_page, name='abc'),
    path('system/', system_settings, name='system-settings'),
    path('access-control/', access_control, name='access-control'),
    path('delete-sale/<int:id>/', delete_sale, name='delete_sale'),
    path('delete-transaction/<int:id>/', delete_transaction, name='delete_transaction'),
]

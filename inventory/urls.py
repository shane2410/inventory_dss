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
    multilevel_bom_import,
    # MongoDB APIs
    api_mongodb_materials,
    api_mongodb_material_detail,
    api_mongodb_products,
    api_mongodb_product_detail,
    api_mongodb_transactions,
    api_mongodb_material_transactions,
    api_mongodb_test,
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
    path('import/multilevel-bom/', multilevel_bom_import, name='import-multilevel-bom'),

    path('alert/', alert, name='alert'),
    path('forecast/', forecast, name='forecast'),
    path('abc/', abc_page, name='abc'),
    path('system/', system_settings, name='system-settings'),
    path('access-control/', access_control, name='access-control'),
    path('delete-sale/<int:id>/', delete_sale, name='delete_sale'),
    path('delete-transaction/<int:id>/', delete_transaction, name='delete_transaction'),
    
    # MongoDB API endpoints
    path('api/mongodb/materials/', api_mongodb_materials, name='api-mongodb-materials'),
    path('api/mongodb/materials/<str:material_id>/', api_mongodb_material_detail, name='api-mongodb-material-detail'),
    path('api/mongodb/products/', api_mongodb_products, name='api-mongodb-products'),
    path('api/mongodb/products/<str:product_id>/', api_mongodb_product_detail, name='api-mongodb-product-detail'),
    path('api/mongodb/transactions/', api_mongodb_transactions, name='api-mongodb-transactions'),
    path('api/mongodb/materials/<str:material_id>/transactions/', api_mongodb_material_transactions, name='api-mongodb-material-transactions'),
    path('api/mongodb/test/', api_mongodb_test, name='api-mongodb-test'),
]

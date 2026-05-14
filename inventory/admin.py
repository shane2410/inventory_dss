from django.contrib import admin

from .models import Material, Product, ProductRatio, Transaction

admin.site.site_header = "Quản trị hệ thống tồn kho"
admin.site.site_title = "Quản trị tồn kho"
admin.site.index_title = "Bảng điều khiển quản trị"

admin.site.register(Material)
admin.site.register(Product)
admin.site.register(ProductRatio)
admin.site.register(Transaction)

#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_dss.settings')
django.setup()

from inventory.models import Product, DisaggregatedPlan, CustomerOrder

# Tạo test data
try:
    # Kiểm tra có sản phẩm nào không
    products = Product.objects.all()
    print(f"Số lượng sản phẩm: {products.count()}")
    
    if products.count() > 0:
        product = products.first()
        print(f"Sản phẩm test: {product.name} (ID: {product.id})")
        
        # Tạo dữ liệu DisaggregatedPlan giả để test
        for month in range(5, 13):
            DisaggregatedPlan.objects.get_or_create(
                product=product,
                month=month,
                defaults={'qty': 1000 * (month - 4)}  # 1000, 2000, 3000, ...
            )
        
        demand_count = DisaggregatedPlan.objects.filter(product=product).count()
        print(f"Số kỳ nhu cầu: {demand_count}")
        
        # Tạo đơn hàng giả
        for month in [5, 7, 9, 11]:
            CustomerOrder.objects.get_or_create(
                product=product,
                month=month,
                defaults={'qty': 500}
            )
        
        order_count = CustomerOrder.objects.filter(product=product).count()
        print(f"Số đơn hàng: {order_count}")
        
        # Test hàm services
        from inventory.services import get_demand_by_product, get_orders_by_product, ppa_lot_sizing, calculate_mps, calculate_epp
        
        demand = get_demand_by_product(product.id)
        orders = get_orders_by_product(product.id)
        
        print(f"\nDemand: {demand}")
        print(f"Orders: {orders}")
        
        C = 40000000
        H = 250
        epp = calculate_epp(C, H)
        print(f"\nEPP: {epp}")
        
        lots = ppa_lot_sizing(demand, C, H)
        print(f"Lots (MPS): {lots}")
        
        projected, atp = calculate_mps(demand, orders, lots)
        print(f"Projected: {projected}")
        print(f"ATP: {atp}")
        
        print("\n✓ Test thành công!")
    else:
        print("⚠ Không có sản phẩm nào trong database")
        
except Exception as e:
    import traceback
    print(f"✗ Lỗi: {e}")
    traceback.print_exc()

from django.shortcuts import render, redirect, get_object_or_404
from functools import wraps
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum
from openpyxl import Workbook, load_workbook
from .models import Product, Material, SalesData, Transaction
from .forms import ImportDataForm
from .services import run_dss
from .services import forecast_product
from .services import abc_classification, forecast_product
from .recommendations import build_dashboard_recommendations, build_inventory_alert_recommendations
from .models import Product, BOM
from datetime import datetime, timedelta, date
from .permissions import (
    ALL_ROLE_CODES,
    ROLE_ADMIN,
    ROLE_FORM_CHOICES,
    ROLE_MANAGER,
    ROLE_OTHER,
    ROLE_STAFF,
    assign_user_role,
    create_user_with_role,
    ensure_role_groups,
    get_user_role_code,
    get_user_role_label,
    role_required,
)


def _apply_recommendation_filters(recommendations, urgency='ALL', abc='ALL', action='ALL'):
    filtered = recommendations

    if urgency != 'ALL':
        filtered = [item for item in filtered if item.get('urgency') == urgency]

    if abc != 'ALL':
        filtered = [item for item in filtered if item.get('abc_class') == abc]

    if action != 'ALL':
        filtered = [item for item in filtered if item.get('action') == action]
    return filtered


def csrf_failure(request, reason=""):
    message = "Phiên làm việc đã hết hạn hoặc token bảo mật không hợp lệ. Vui lòng tải lại trang và thử lại."
    return render(request, 'inventory/login.html', {
        'error_message': message,
    }, status=403)


session_name_required = role_required(*ALL_ROLE_CODES)
admin_required = role_required(ROLE_ADMIN)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    User = get_user_model()
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser(username='admin', password='123')

    error_message = None

    if request.method == 'POST':
        username = request.POST.get('display_name', '').strip()
        password = request.POST.get('display_password', '')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            request.session['display_name'] = user.username
            request.session['is_admin'] = user.is_superuser
            request.session['user_role'] = get_user_role_code(user)
            return redirect('dashboard')

        error_message = "Tài khoản hoặc mật khẩu không chính xác."

    return render(request, 'inventory/login.html', {
        'error_message': error_message,
    })


def logout_view(request):
    logout(request)
    return redirect('login')

# =========================
# DASHBOARD (SALES + TRANSACTION)
# =========================
@session_name_required
def dashboard(request):

    # =========================
    # POST HANDLE
    # =========================
    if request.method == 'POST':

        # ===== ADD SALES =====
        if 'add_sales' in request.POST:
            product_id = request.POST.get('product_id')
            quantity = request.POST.get('quantity')
            date_input = request.POST.get('date')

            # ép kiểu quantity
            try:
                quantity = int(quantity)
            except:
                quantity = 0

            # ép kiểu date
            try:
                date_input = datetime.strptime(date_input, "%Y-%m-%d").date()
            except:
                date_input = None

            if product_id and quantity > 0 and date_input:
                SalesData.objects.create(
                    product_id=product_id,
                    quantity=quantity,
                    date=date_input
                )

        # ===== ADD TRANSACTION =====
        elif 'add_transaction' in request.POST:
            material_id = request.POST.get('material_id')
            quantity = request.POST.get('quantity')
            t_type = request.POST.get('transaction_type')
            date_input = request.POST.get('date')

            try:
                quantity = int(quantity)
            except:
                quantity = 0

            try:
                date_input = datetime.strptime(date_input, "%Y-%m-%d").date()
            except:
                date_input = None

            if material_id and quantity > 0 and date_input:
                material = Material.objects.get(id=material_id)

                # update tồn kho
                if t_type == 'IN':
                    material.on_hand += quantity
                elif t_type == 'OUT':
                    if material.on_hand >= quantity:
                        material.on_hand -= quantity

                material.save()

                # lưu transaction
                Transaction.objects.create(
                    material=material,
                    quantity=quantity,
                    transaction_type=t_type,
                    date=date_input
                )

    # =========================
    # GET DATA
    # =========================
    products = Product.objects.all()
    materials = Material.objects.all()

    # 👉 lấy mới nhất + ổn định thứ tự
    sales_list = SalesData.objects.all().order_by('-date', '-id')[:10]
    transaction_list = Transaction.objects.all().order_by('-id')[:10]

    # =========================
    # TOP 5 PRODUCTS BY REVENUE (unit_price derived from BOM materials)
    # revenue = unit_price * total_quantity_sold
    # =========================
    sales_agg = list(
        SalesData.objects
        .values('product_id', 'product__name')
        .annotate(total_quantity=Sum('quantity'))
    )

    product_revenues = []
    total_revenue = 0.0

    for row in sales_agg:
        product_id = row.get('product_id')
        product_name = row.get('product__name')
        qty = float(row.get('total_quantity') or 0)

        # compute unit price from BOM: sum(material.price_cost * quantity_per_unit)
        boms = BOM.objects.filter(product_id=product_id).select_related('material')
        unit_price = 0.0
        for bom in boms:
            if bom.material and bom.material.price_cost:
                unit_price += float(bom.quantity_per_unit or 0) * float(bom.material.price_cost or 0)

        revenue = qty * unit_price
        total_revenue += revenue

        product_revenues.append({
            'product_id': product_id,
            'name': product_name,
            'quantity': qty,
            'unit_price': unit_price,
            'revenue': revenue,
        })

    # sort by revenue desc and take top 5
    product_revenues.sort(key=lambda x: x['revenue'], reverse=True)
    top5 = product_revenues[:5]

    top_sales_chart_labels = []
    top_sales_chart_values = []
    top_sales_chart_cumulative_percent = []

    for item in top5:
        # percent of total revenue for this product (not cumulative)
        percent = (item['revenue'] / total_revenue * 100) if total_revenue else 0

        top_sales_chart_labels.append(item['name'])
        top_sales_chart_values.append(round(item['revenue'], 2))
        top_sales_chart_cumulative_percent.append(round(percent, 1))

    top_sales_chart_data = {
        'labels': top_sales_chart_labels,
        'values': top_sales_chart_values,
        'cumulative_percent': top_sales_chart_cumulative_percent,
        'total_revenue': round(float(total_revenue), 2),
    }

    # 👉 Gợi ý ngày nhập gần nhất
    last_sale = SalesData.objects.order_by('-date').first()

    if last_sale:
        min_date = last_sale.date.strftime("%Y-%m-%d")
    else:
        min_date = None

    today = date.today().strftime("%Y-%m-%d")

    # =========================
    # ABC VALUE SUMMARY (TRANSACTION OUT)
    # =========================
    transaction_out_data = (
        Transaction.objects
        .filter(transaction_type='OUT')
        .values('material')
        .annotate(total_quantity=Sum('quantity'))
    )

    demand_map = {
        item['material']: item['total_quantity'] or 0
        for item in transaction_out_data
    }

    abc_material_list = []
    for material in materials:
        abc_material_list.append({
            'material': material,
            'demand': demand_map.get(material.id, 0),
        })

    abc_map = abc_classification(abc_material_list)
    abc_value_total = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    abc_counts = {'A': 0, 'B': 0, 'C': 0}

    for item in abc_material_list:
        material = item['material']
        demand = item['demand'] or 0
        abc_class = abc_map.get(material.id)

        if abc_class:
            abc_value_total[abc_class] += float(demand) * float(material.price_cost)
            # count materials per ABC class (for pie chart proportions)
            if abc_class in abc_counts:
                abc_counts[abc_class] += 1

    abc_chart_data = {
        'labels': ['A', 'B', 'C'],
        'values': [
            round(abc_value_total['A'], 2),
            round(abc_value_total['B'], 2),
            round(abc_value_total['C'], 2),
        ],
        'colors': ['#4b5f70', '#4e8b90', '#4f8e74'],
        'total': round(sum(abc_value_total.values()), 2),
    }

    selected_urgency = request.GET.get('urgency', 'ALL').upper()
    selected_abc = request.GET.get('abc', 'ALL').upper()
    selected_action = request.GET.get('action', 'ALL').upper()

    recommendations_all, recommendation_summary = build_dashboard_recommendations(limit=200)
    recommendations_filtered_all = recommendations_all
    recommendations = recommendations_filtered_all
    recommendation_display = f"{len(recommendations)} URGENT"

    return render(request, 'inventory/dashboard.html', {
        'products': products,
        'materials': materials,

        'total_products': products.count(),
        'total_materials': materials.count(),

        'sales_list': sales_list,
        'transaction_list': transaction_list,
        'top_sales_chart_data': top_sales_chart_data,
        'recommendations': recommendations,
        'recommendation_summary': recommendation_summary,
        'recommendation_total': len(recommendations_filtered_all),
        'recommendation_filtered': len(recommendations),
        'recommendation_display': recommendation_display,
        'min_date': min_date,
        'today': today,
        'abc_value_total': abc_value_total,
        'abc_value_sum': sum(abc_value_total.values()),
        'abc_counts': abc_counts,
        'abc_count_total': sum(abc_counts.values()),
        'abc_chart_data': abc_chart_data,
    })


@session_name_required
def recommendation_api(request):
    selected_urgency = request.GET.get('urgency', 'ALL').upper()
    selected_abc = request.GET.get('abc', 'ALL').upper()
    selected_action = request.GET.get('action', 'ALL').upper()

    recommendations, summary = build_dashboard_recommendations(limit=200)
    filtered = _apply_recommendation_filters(
        recommendations,
        urgency=selected_urgency,
        abc=selected_abc,
        action=selected_action,
    )
    payload = [item['json'] for item in filtered]

    return JsonResponse({
        'summary': summary,
        'filters': {
            'urgency': selected_urgency,
            'abc': selected_abc,
            'action': selected_action,
            'count': len(payload),
        },
        'recommendations': payload,
    }, json_dumps_params={'ensure_ascii': False, 'indent': 2})


@session_name_required
def recommendation_excel_api(request):
    selected_urgency = request.GET.get('urgency', 'ALL').upper()
    selected_abc = request.GET.get('abc', 'ALL').upper()
    selected_action = request.GET.get('action', 'ALL').upper()

    recommendations, _ = build_dashboard_recommendations(limit=500)
    filtered = _apply_recommendation_filters(
        recommendations,
        urgency=selected_urgency,
        abc=selected_abc,
        action=selected_action,
    )

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Recommendations'

    headers = [
        'item',
        'material_name',
        'abc_class',
        'action',
        'quantity',
        'urgency',
        'ip',
        'rop',
        's',
        'message',
    ]
    worksheet.append(headers)

    for item in filtered:
        worksheet.append([
            item.get('item'),
            item.get('material_name'),
            item.get('abc_class'),
            item.get('action'),
            item.get('quantity'),
            item.get('urgency'),
            item.get('ip'),
            item.get('rop'),
            item.get('s'),
            item.get('message'),
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="dashboard_recommendations.xlsx"'
    workbook.save(response)

    return response


# =========================
# DELETE SALE
# =========================
@session_name_required
def delete_sale(request, id):
    sale = get_object_or_404(SalesData, id=id)
    sale.delete()
    return redirect('dashboard')


@session_name_required
def delete_transaction(request, id):
    t = get_object_or_404(Transaction, id=id)
    t.delete()
    return redirect('dashboard')


# =========================
# PRODUCT + DSS
# =========================
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_STAFF)
def product_list(request):
    products = Product.objects.all()

    results = []
    selected_product = None

    if request.method == 'POST':
        product_id = request.POST.get('product_id')

        if product_id:
            selected_product = Product.objects.get(id=product_id)
            results = run_dss(product_id)

    return render(request, 'inventory/product_list.html', {
        'products': products,
        'results': results,
        'selected_product': selected_product,
    })


# =========================
# MATERIAL LIST
# =========================
@role_required(ROLE_ADMIN, ROLE_MANAGER)
def material_list(request):
    materials = Material.objects.all()

    data = []
    for m in materials:
        data.append({
            'material_id': m.source_id or f'NVL{m.id}',
            'name': m.name,
            'on_hand': m.on_hand,
            'on_order': m.on_order,
            'inventory_position': m.on_hand + m.on_order,
            'leadtime': m.leadtime,
            'holding_cost': m.holding_cost,
            'ordering_cost': m.ordering_cost,
            'price_cost': m.price_cost,
        })

    return render(request, 'inventory/material_list.html', {
        'materials': data
    })


# =========================
# OTHER PAGES
# =========================
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_STAFF)
def alert(request):
    alerts, summary = build_inventory_alert_recommendations()

    return render(request, 'inventory/alert.html', {
        "alerts": alerts,
        "summary": summary,
    })


@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_STAFF)
def forecast(request):
    from .models import Product, BOM
    from .services import forecast_product
    from collections import defaultdict
    import math

    products = Product.objects.all()

    selected_product = None
    product_result = None
    material_results = []
    forecast_7 = []

    # =========================
    # PRODUCT FORECAST
    # =========================
    if request.method == 'POST':
        product_id = request.POST.get('product_id')

        if product_id:
            selected_product = Product.objects.get(id=product_id)

            mean, std, forecast_7, mae, rmse, mape = forecast_product(product_id)

            mape_value = float(round(mape, 2))
            if mape_value < 10:
                mape_level = "good"
                evaluation_class = "evaluation-good"
                evaluation_icon = "fas fa-check"
                evaluation_message = (
                    "Mô hình có độ chính xác rất cao (MAPE < 10%). "
                    "Kết quả dự báo rất đáng tin cậy."
                )
            elif mape_value < 20:
                mape_level = "medium"
                evaluation_class = "evaluation-medium"
                evaluation_icon = "fas fa-info"
                evaluation_message = (
                    "Mô hình ở mức chấp nhận được (10% - 20%). "
                    "Cần theo dõi thêm biến động thực tế."
                )
            else:
                mape_level = "bad"
                evaluation_class = "evaluation-bad"
                evaluation_icon = "fas fa-exclamation-triangle"
                evaluation_message = (
                    "Độ sai số cao (MAPE > 20%). Nhu cầu sản phẩm này có biến động "
                    "quá lớn, mô hình hiện tại không phù hợp."
                )

            product_result = {
                "name": selected_product.name,
                "mean": round(mean, 2),
                "std": round(std, 2),
                "forecast_7": [round(x, 2) for x in forecast_7],
                "mae": round(mae, 2),
                "rmse": round(rmse, 2),
                "mape": mape_value,
                "mape_level": mape_level,
                "evaluation_class": evaluation_class,
                "evaluation_icon": evaluation_icon,
                "evaluation_message": evaluation_message,
            }

    # =========================
    # 🔥 MATERIAL AGGREGATE (LUÔN CHẠY)
    # =========================
    material_dict = defaultdict(lambda: {
        "material": "",
        "material_id": "",
        "mean": 0,
        "variance": 0,
        "forecast_7": [0] * 7
    })

    for product in Product.objects.all():
        p_mean, p_std, p_f7, *_ = forecast_product(product.id)

        boms = BOM.objects.filter(product=product)

        for bom in boms:
            material = bom.material
            material_key = material.id

            material_dict[material_key]["material"] = material.name
            material_dict[material_key]["material_id"] = material.source_id or f"NVL{material.id}"

            material_dict[material_key]["mean"] += p_mean * bom.quantity_per_unit
            material_dict[material_key]["variance"] += (p_std * bom.quantity_per_unit) ** 2

            for i in range(7):
                material_dict[material_key]["forecast_7"][i] += p_f7[i] * bom.quantity_per_unit

    # convert
    # 🔥 chỉ lấy material thuộc product đang chọn
    selected_material_ids = set(
        BOM.objects.filter(product=selected_product).values_list('material_id', flat=True)
    )

    material_results = []

    for material_id, data in material_dict.items():
        if material_id in selected_material_ids:  # 👈 CHỈ HIỂN THỊ MATERIAL CỦA PRODUCT ĐANG CHỌN
            material_results.append({
                "material": data["material"],
                "material_id": data["material_id"],
                "mean": round(data["mean"], 2),
                "std": round(math.sqrt(data["variance"]), 2),
                "forecast_7": [round(x, 2) for x in data["forecast_7"]]
            })

    # =========================
    # 🔥 LUÔN RETURN
    # =========================
    return render(request, 'inventory/forecast.html', {
        "products": products,
        "selected_product": selected_product,
        "product_result": product_result,
        "material_results": material_results,
        "forecast_7": forecast_7
    })
from .services import abc_classification, forecast_product
from .models import Product, BOM

@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_STAFF)
def abc_page(request):
    from .models import Product, Material, Transaction, BOM
    from django.db.models import Sum
    from .services import abc_classification

    products = Product.objects.all()

    product_id = request.GET.get("product_id")
    abc_filter = request.GET.get("abc")

    selected_product = None
    results = []

    # =========================
    # 🔵 1. ABC TOÀN HỆ THỐNG (THEO TRANSACTION - TỐI ƯU)
    # =========================
    material_list = []

    # 👉 gom transaction 1 lần (KHÔNG loop)
    transaction_data = (
        Transaction.objects
        .filter(transaction_type='OUT')
        .values('material')
        .annotate(total=Sum('quantity'))
    )

    # 👉 convert thành dict cho nhanh
    demand_map = {
        item['material']: item['total']
        for item in transaction_data
    }

    materials = Material.objects.all()

    for m in materials:
        demand = demand_map.get(m.id, 0)

        material_list.append({
            "material": m,
            "demand": demand  # 🔥 giữ tên mean cho abc_classification
        })

    # 👉 ABC
    abc_all = abc_classification(material_list)

    # 👉 đếm tổng
    abc_total = {"A": 0, "B": 0, "C": 0}

    for item in material_list:
        m = item["material"]
        cat = abc_all.get(m.id)

        if cat:
            abc_total[cat] += 1

    # =========================
    # 🔴 FILTER MATERIAL
    # =========================
    filtered_materials = []

    for item in material_list:
        m = item["material"]
        demand = item["demand"]
        abc = abc_all.get(m.id, "-")

        if not abc_filter or abc == abc_filter:
            filtered_materials.append({
                "material_id": m.source_id or f"NVL{m.id}",
                "material": m.name,
                "demand": demand,
                "price": m.price_cost,
                "value": demand * m.price_cost,
                "abc": abc
            })

    # =========================
    # 🟢 ABC THEO PRODUCT
    # =========================
    if product_id:
        selected_product = Product.objects.get(id=product_id)

        boms = BOM.objects.filter(product=selected_product).select_related('material')

        for bom in boms:
            m = bom.material
            demand = demand_map.get(m.id, 0)

            results.append({
                "material_id": m.source_id or f"NVL{m.id}",
                "material": m.name,
                "demand": demand,
                "price": m.price_cost,
                "value": demand * m.price_cost,
                "abc": abc_all.get(m.id, "-")
            })

    return render(request, "inventory/abc.html", {
        "products": products,
        "selected_product": selected_product,
        "results": results,
        "filtered_materials": filtered_materials,
        "abc_total": abc_total,
        "selected_abc": abc_filter
    })


@admin_required
def system_settings(request):
    return render(request, "inventory/system_settings.html")


@admin_required
def access_control(request):
    User = get_user_model()
    ensure_role_groups()
    error_message = None
    success_message = None

    if request.method == 'POST':
        role_update_user_id = request.POST.get('update_role_user_id')
        delete_user_id = request.POST.get('delete_user_id')

        if role_update_user_id:
            try:
                target_user = User.objects.get(id=role_update_user_id)
            except User.DoesNotExist:
                error_message = 'Tài khoản cần cập nhật không tồn tại.'
            else:
                if target_user.id == request.user.id:
                    error_message = 'Bạn không thể tự thay đổi vai trò của tài khoản đang đăng nhập.'
                else:
                    selected_role = request.POST.get('role_code', ROLE_OTHER)
                    if selected_role == ROLE_ADMIN:
                        if not target_user.is_superuser:
                            target_user.is_superuser = True
                            target_user.save(update_fields=['is_superuser'])
                        target_user.groups.clear()
                    else:
                        if target_user.is_superuser:
                            target_user.is_superuser = False
                            target_user.save(update_fields=['is_superuser'])
                        assign_user_role(target_user, selected_role)
                    success_message = f'Đã cập nhật vai trò cho {target_user.username}.'

        elif delete_user_id:
            if not request.user.is_superuser:
                error_message = 'Chỉ admin mới có quyền xóa tài khoản.'
            else:
                try:
                    target_user = User.objects.get(id=delete_user_id)
                except User.DoesNotExist:
                    error_message = 'Tài khoản cần xóa không tồn tại.'
                else:
                    if target_user.id == request.user.id:
                        error_message = 'Bạn không thể tự xóa tài khoản đang đăng nhập.'
                    elif target_user.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
                        error_message = 'Không thể xóa admin cuối cùng của hệ thống.'
                    else:
                        deleted_username = target_user.username
                        target_user.delete()
                        success_message = f'Đã xóa tài khoản {deleted_username}.'
        else:
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            role_code = request.POST.get('role_code', ROLE_OTHER)

            if not username or not password:
                error_message = 'Vui lòng nhập đầy đủ tài khoản và mật khẩu.'
            elif User.objects.filter(username=username).exists():
                error_message = 'Tài khoản đã tồn tại, vui lòng chọn tên khác.'
            else:
                create_user_with_role(username=username, password=password, role_code=role_code)
                success_message = f'Đã tạo tài khoản {username} thành công.'

    users = []
    for user in User.objects.all().order_by('username'):
        users.append({
            'id': user.id,
            'username': user.username,
            'is_superuser': user.is_superuser,
            'is_active': user.is_active,
            'role_code': get_user_role_code(user),
            'role_label': get_user_role_label(user),
        })

    return render(request, 'inventory/access_control.html', {
        'users': users,
        'error_message': error_message,
        'success_message': success_message,
        'role_choices': ROLE_FORM_CHOICES,
        'default_role_code': ROLE_OTHER,
    })


# =========================
# IMPORT DATA FROM EXCEL
# =========================
@role_required(ROLE_ADMIN, ROLE_MANAGER, ROLE_STAFF)
def import_data(request):
    def _parse_excel_date(raw_value):
        if isinstance(raw_value, datetime):
            return raw_value.date()
        if isinstance(raw_value, date):
            return raw_value
        if isinstance(raw_value, str):
            text = raw_value.strip()
            for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
        return None

    def _parse_transaction_type(raw_value):
        text = str(raw_value).strip().upper()
        if text in ('IN', 'NHAP', 'NHAP KHO'):
            return 'IN'
        if text in ('OUT', 'XUAT', 'XUAT KHO'):
            return 'OUT'
        return None

    form = ImportDataForm()
    result_message = None
    error_message = None
    products = Product.objects.all()
    materials = Material.objects.all()

    last_sale = SalesData.objects.order_by('-date').first()
    min_date = last_sale.date.strftime("%Y-%m-%d") if last_sale else None
    today = date.today().strftime("%Y-%m-%d")

    if request.method == 'POST':
        if 'add_sales' in request.POST:
            product_id = request.POST.get('product_id')
            quantity = request.POST.get('quantity')
            date_input = request.POST.get('date')

            try:
                quantity = int(quantity)
            except Exception:
                quantity = 0

            try:
                date_input = datetime.strptime(date_input, "%Y-%m-%d").date()
            except Exception:
                date_input = None

            if product_id and quantity > 0 and date_input:
                SalesData.objects.create(
                    product_id=product_id,
                    quantity=quantity,
                    date=date_input
                )
                result_message = 'Đã thêm doanh số thành công.'
            else:
                error_message = 'Dữ liệu nhập doanh số không hợp lệ.'

        elif 'add_transaction' in request.POST:
            material_id = request.POST.get('material_id')
            quantity = request.POST.get('quantity')
            t_type = request.POST.get('transaction_type')
            date_input = request.POST.get('date')

            try:
                quantity = int(quantity)
            except Exception:
                quantity = 0

            try:
                date_input = datetime.strptime(date_input, "%Y-%m-%d").date()
            except Exception:
                date_input = None

            if material_id and quantity > 0 and date_input and t_type in ('IN', 'OUT'):
                material = Material.objects.get(id=material_id)

                if t_type == 'IN':
                    material.on_hand += quantity
                elif t_type == 'OUT' and material.on_hand >= quantity:
                    material.on_hand -= quantity

                material.save()

                Transaction.objects.create(
                    material=material,
                    quantity=quantity,
                    transaction_type=t_type,
                    date=date_input
                )
                result_message = 'Đã thêm giao dịch thành công.'
            else:
                error_message = 'Dữ liệu nhập giao dịch không hợp lệ.'

        elif 'import_excel' in request.POST:
            form = ImportDataForm(request.POST, request.FILES)
            if form.is_valid():
                import_type = form.cleaned_data['import_type']
                excel_file = request.FILES['file']

                try:
                    wb = load_workbook(excel_file)
                    ws = wb.active

                    if import_type == 'sales':
                        # Expected columns: product_name, date, quantity
                        rows_imported = 0
                        for row in ws.iter_rows(min_row=2, values_only=True):
                            if row[0] is None:
                                continue
                            try:
                                product_name = str(row[0]).strip()
                                date_obj = _parse_excel_date(row[1])
                                quantity = int(row[2])

                                if not date_obj:
                                    continue

                                product = Product.objects.filter(name=product_name).first() or \
                                    Product.objects.filter(source_id=product_name).first()

                                if product:
                                    SalesData.objects.create(
                                        product=product,
                                        date=date_obj,
                                        quantity=quantity
                                    )
                                    rows_imported += 1
                            except Exception:
                                continue

                        result_message = f'✓ Đã import {rows_imported} bản ghi bán hàng thành công.'

                    elif import_type == 'transaction':
                        # Expected columns: material_name, quantity, transaction_type, date
                        rows_imported = 0
                        for row in ws.iter_rows(min_row=2, values_only=True):
                            if row[0] is None:
                                continue
                            try:
                                material_name = str(row[0]).strip()
                                quantity = int(row[1])
                                transaction_type = _parse_transaction_type(row[2])
                                date_obj = _parse_excel_date(row[3])

                                if not transaction_type or not date_obj:
                                    continue

                                material = Material.objects.filter(name=material_name).first() or \
                                    Material.objects.filter(source_id=material_name).first()

                                if material:
                                    Transaction.objects.create(
                                        material=material,
                                        quantity=quantity,
                                        transaction_type=transaction_type,
                                        date=date_obj
                                    )
                                    rows_imported += 1
                            except Exception:
                                continue

                        result_message = f'✓ Đã import {rows_imported} bản ghi giao dịch thành công.'

                except Exception as e:
                    error_message = f'Lỗi xử lý file: {str(e)}'
            else:
                error_message = 'Vui lòng chọn loại dữ liệu và file Excel hợp lệ.'

    return render(request, 'inventory/import_data.html', {
        'form': form,
        'result_message': result_message,
        'error_message': error_message,
        'products': products,
        'materials': materials,
        'min_date': min_date,
        'today': today,
    })

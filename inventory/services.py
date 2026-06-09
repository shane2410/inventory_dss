import pandas as pd
import numpy as np
import math
from collections import defaultdict
from inventory.models import SalesData, BOM, Material, Product, ProductRatio, DisaggregatedPlan, CustomerOrder, PlanningItem, MultiLevelBOMEdge


# =========================
# 1. FORECAST (CÓ XỬ LÝ DATA)
# =========================
def forecast_product(product_id, sales_qs=None):
    if sales_qs is None:
        sales = SalesData.objects.filter(product_id=product_id).values('date', 'quantity')
    else:
        sales = sales_qs.filter(product_id=product_id).values('date', 'quantity')
    df = pd.DataFrame(list(sales))

    if df.empty or len(df) < 5:
        return 0, 0, [0] * 7, 0, 0, 0

    # ===== CLEAN =====
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    df = df[df['quantity'] >= 0]

    # ===== GROUP =====
    df = df.groupby('date')['quantity'].sum().reset_index()

    # ===== FILL MISSING DATE =====
    full_range = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq='D')
    df = df.set_index('date').reindex(full_range, fill_value=0)
    df.index.name = 'date'

    # ===== OUTLIER =====
    q1 = df['quantity'].quantile(0.25)
    q3 = df['quantity'].quantile(0.75)
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    df['quantity'] = df['quantity'].clip(lower=lower, upper=upper)

    # ===== SMOOTH =====
    df['quantity_smooth'] = df['quantity'].rolling(window=3, min_periods=1).mean()

    # ✅ QUAN TRỌNG: đảm bảo series là float + index chuẩn
    series = df['quantity_smooth'].astype(float)

    # ===== FORECAST =====
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        model = ExponentialSmoothing(
            series,
            trend='add',
            seasonal=None,
            initialization_method="estimated"
        )

        # Use a simple, compatible fit call; older/newer statsmodels
        # versions may not accept disp/maxiter kwargs.
        fit = model.fit(optimized=True)

        forecast = fit.forecast(7)
        # ensure forecast is a pandas Series so downstream code can use .values
        forecast = pd.Series(forecast)

        mean = float(forecast.mean())
        std = float(series.std())

        forecast_list = forecast.tolist()

    except Exception as e:
        print("Forecast error:", e)

        mean = float(series.mean())
        std = float(series.std(ddof=1))
        forecast_list = [mean] * 7  # fallback forecast values
        forecast = pd.Series(forecast_list)

    if np.isnan(std) or std < 0:
        std = 0

    if np.isnan(std):
        std = 0
    # ===== CALCULATE ERROR =====
    actual = series[-7:]  # dữ liệu thật 7 ngày gần nhất

    if len(actual) == len(forecast):
        mae = np.mean(np.abs(actual.values - forecast.values))
        rmse = np.sqrt(np.mean((actual.values - forecast.values) ** 2))

        # tránh chia 0
        mape = np.mean(
            np.abs((actual.values - forecast.values) / np.maximum(actual.values, 1))
        ) * 100
    else:
        mae, rmse, mape = 0, 0, 0

    return mean, std, forecast_list, mae, rmse, mape


def aggregate_material_demand(source='operations'):
    demand_stats = defaultdict(lambda: {"mean": 0.0, "variance": 0.0})

    from .models import SalesData

    sales_scope = SalesData.objects.filter(source=source)

    product_forecasts = {}
    products_with_sales = set(
        sales_scope.values_list('product_id', flat=True).distinct()
    )

    for product_id in products_with_sales:
        try:
            mean, std, _, _, _, _ = forecast_product(product_id, sales_qs=sales_scope)
            product_forecasts[product_id] = (
                max(float(mean or 0), 0.0),
                max(float(std or 0), 0.0),
            )
        except Exception:
            values = list(
                sales_scope.filter(product_id=product_id)
                .values_list('quantity', flat=True)
            )
            if values:
                mean = sum(float(q or 0) for q in values) / len(values)
                variance = sum((float(q or 0) - mean) ** 2 for q in values) / len(values)
                std = float(np.sqrt(max(variance, 0.0)))
            else:
                mean, std = 0.0, 0.0

            product_forecasts[product_id] = (
                max(float(mean or 0), 0.0),
                max(float(std or 0), 0.0),
            )

    # Fetch BOMs once and deduplicate by (material, product) to avoid double-count
    all_boms = list(BOM.objects.select_related("material", "product"))
    seen_bom_pairs = set()
    deduped_boms = []
    for bom in all_boms:
        key = (bom.material_id, bom.product_id)
        if key not in seen_bom_pairs:
            seen_bom_pairs.add(key)
            deduped_boms.append(bom)

    for bom in deduped_boms:
        mean, std = product_forecasts.get(bom.product_id, (0.0, 0.0))
        qty = float(bom.quantity_per_unit or 0)
        if qty <= 0:
            continue

        demand_stats[bom.material_id]["mean"] += mean * qty
        demand_stats[bom.material_id]["variance"] += (std * qty) ** 2

    return demand_stats


# =========================
# 3. INVENTORY ANALYSIS
# =========================
def inventory_analysis(material, mean, std):

    ip = material.on_hand + material.on_order

    L = max(int(material.leadtime), 1)

    z = 1.65

    # Safety Stock
    ss = z * std * np.sqrt(L)

    # ✅ FIX LỖI Ở ĐÂY
    demand_L = mean * L   # ❌ KHÔNG dùng forecast list nữa

    rop = demand_L + ss

    action = "ORDER" if ip < rop else "OK"

    return {
        "ip": ip,
        "ss": round(ss, 2),
        "rop": round(rop, 2),
        "action": action
    }


def forecast_product_monthly(product_id, sales_qs=None):
    """Forecast monthly sales for a product and predict next 8 months.

    Returns: mean, std, forecast_list(8), mae, rmse, mape
    """
    if sales_qs is None:
        sales = SalesData.objects.filter(product_id=product_id).values('date', 'quantity')
    else:
        sales = sales_qs.filter(product_id=product_id).values('date', 'quantity')
    df = pd.DataFrame(list(sales))

    if df.empty or len(df) < 3:
        return 0, 0, [0] * 8, 0, 0, 0

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    df = df[df['quantity'] >= 0]

    # Group by month
    df = df.set_index('date').groupby(pd.Grouper(freq='M'))['quantity'].sum().reset_index()

    # fill missing months
    full_range = pd.date_range(start=df['date'].min(), end=df['date'].max(), freq='M')
    df = df.set_index('date').reindex(full_range, fill_value=0)
    df.index.name = 'date'

    # outlier clip
    q1 = df['quantity'].quantile(0.25)
    q3 = df['quantity'].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    df['quantity'] = df['quantity'].clip(lower=lower, upper=upper)

    # smooth
    df['quantity_smooth'] = df['quantity'].rolling(window=3, min_periods=1).mean()

    series = df['quantity_smooth'].astype(float)

    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        model = ExponentialSmoothing(
            series,
            trend='add',
            seasonal=None,
            initialization_method="estimated"
        )

        fit = model.fit(optimized=True)

        forecast = fit.forecast(8)
        forecast = pd.Series(forecast)

        mean = float(forecast.mean())
        std = float(series.std())
        forecast_list = forecast.tolist()

    except Exception as e:
        print("Monthly forecast error:", e)
        mean = float(series.mean())
        std = float(series.std(ddof=1))
        forecast_list = [mean] * 8
        forecast = pd.Series(forecast_list)

    if np.isnan(std) or std < 0:
        std = 0

    # error metrics: compare last available months
    actual = series[-8:]
    if len(actual) == len(forecast):
        mae = np.mean(np.abs(actual.values - forecast.values))
        rmse = np.sqrt(np.mean((actual.values - forecast.values) ** 2))
        mape = np.mean(np.abs((actual.values - forecast.values) / np.maximum(actual.values, 1))) * 100
    else:
        mae, rmse, mape = 0, 0, 0

    return mean, std, forecast_list, mae, rmse, mape


def forecast_monthly_total(history_qs=None, forecast_horizon=8):
    """Forecast a total monthly production series from imported month/quantity rows."""
    from .models import MonthlyProductionData

    forecast_horizon = max(1, int(forecast_horizon or 8))

    if history_qs is None:
        history_qs = MonthlyProductionData.objects.filter(
            source=MonthlyProductionData.SOURCE_PLANNING
        )

    df = pd.DataFrame(list(history_qs.values('month', 'quantity')))

    if df.empty or len(df) < 3:
        return 0, 0, [0] * forecast_horizon, 0, 0, 0

    df['month'] = pd.to_datetime(df['month'])
    df = df.sort_values('month')
    df = df[df['quantity'] >= 0]

    df = df.set_index('month').groupby(pd.Grouper(freq='MS'))['quantity'].sum().reset_index()
    full_range = pd.date_range(start=df['month'].min(), end=df['month'].max(), freq='MS')
    df = df.set_index('month').reindex(full_range, fill_value=0)
    df.index.name = 'month'

    q1 = df['quantity'].quantile(0.25)
    q3 = df['quantity'].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    df['quantity'] = df['quantity'].clip(lower=lower, upper=upper)
    df['quantity_smooth'] = df['quantity'].rolling(window=3, min_periods=1).mean()

    series = df['quantity_smooth'].astype(float)

    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        model = ExponentialSmoothing(
            series,
            trend='add',
            seasonal=None,
            initialization_method='estimated'
        )

        fit = model.fit(optimized=True)
        forecast = pd.Series(fit.forecast(forecast_horizon))
        mean = float(forecast.mean())
        std = float(series.std())
        forecast_list = forecast.tolist()

    except Exception as e:
        print('Monthly total forecast error:', e)
        mean = float(series.mean())
        std = float(series.std(ddof=1))
        forecast_list = [mean] * forecast_horizon
        forecast = pd.Series(forecast_list)

    if np.isnan(std) or std < 0:
        std = 0

    actual = series[-forecast_horizon:]
    if len(actual) == len(forecast):
        try:
            mae = float(np.mean(np.abs(actual.values - forecast.values)))
            rmse = float(np.sqrt(np.mean((actual.values - forecast.values) ** 2)))
            mape = float(np.mean(np.abs((actual.values - forecast.values) / np.where(actual.values == 0, 1, actual.values))) * 100)
        except Exception:
            mae = rmse = mape = 0
    else:
        mae = rmse = mape = 0

    return mean, std, forecast_list, mae, rmse, mape


def disaggregate_forecast(forecast_list, start_month='2025-05-01', ratio_qs=None):
    """Split monthly forecast totals into product-level forecasts using stored ratios."""
    if ratio_qs is None:
        ratio_qs = ProductRatio.objects.all()

    start_month = pd.Timestamp(start_month).to_period('M').to_timestamp()
    result = []

    for index, total_qty in enumerate(forecast_list):
        current_month = (start_month + pd.DateOffset(months=index)).to_period('M').to_timestamp()
        month_ratios = ratio_qs.filter(month=current_month).order_by('product_code', 'product_name', 'id')

        month_rows = []
        allocated_total = 0.0
        total_qty_value = float(total_qty or 0)

        for ratio_obj in month_ratios:
            forecast_qty = round(total_qty_value * float(ratio_obj.ratio or 0), 2)
            month_rows.append({
                'product_id': ratio_obj.product_code,
                'product_name': ratio_obj.product_name,
                'ratio': float(ratio_obj.ratio or 0),
                'forecast_qty': forecast_qty,
            })
            allocated_total += forecast_qty

        result.append({
            'month': current_month,
            'month_label': current_month.strftime('%m/%Y'),
            'total_forecast': round(total_qty_value, 2),
            'allocated_total': round(allocated_total, 2),
            'gap': round(total_qty_value - allocated_total, 2),
            'details': month_rows,
        })

    return result

# =========================
# =========================
# 4. COST + GRID SEARCH (FIXED)
# =========================
def total_cost(material, demand, S, ip, ss):
    if demand <= 0:
        return 0

    h = material.holding_cost
    K = material.ordering_cost
    p = material.price_cost

    Q = max(S - ip, 1)

    # Ordering cost
    ordering_cost = K * (demand / Q)

    # 🔥 FIX QUAN TRỌNG: có safety stock
    avg_inventory = ss + Q / 2

    holding_cost = h * avg_inventory

    purchasing_cost = p * demand

    return ordering_cost + holding_cost + purchasing_cost


def optimize_order_quantity(material, demand, ip, rop, ss):

    best_S = None
    min_cost = float('inf')

    # ===== search từ ROP trở lên =====
    start = int(max(rop, ip))
    end = int(start + max(300, demand * 5))

    for S in range(start, end):

        Q = S - ip
        if Q <= 0:
            continue

        cost = total_cost(material, demand, S, ip, ss)

        if cost < min_cost:
            min_cost = cost
            best_S = S

    # fallback
    if best_S is None:
        best_S = rop

    order_Q = max(best_S - ip, 0)

    return round(best_S, 2), round(order_Q, 2), round(min_cost, 2)

# =========================
# 5. ABC CLASSIFICATION
# =========================
def abc_classification(material_list):
    data = []

    for item in material_list:
        value = item['demand'] * item['material'].price_cost

        data.append({
            "material": item['material'],
            "value": value
        })

    df = pd.DataFrame(data)

    if df.empty:
        return {}

    df = df.sort_values(by='value', ascending=False)

    total = df['value'].sum()
    if total == 0:
        return {}

    df['cum_ratio'] = df['value'].cumsum() / total

    result = {}

    for _, row in df.iterrows():
        if row['cum_ratio'] <= 0.8:
            category = 'A'
        elif row['cum_ratio'] <= 0.95:
            category = 'B'
        else:
            category = 'C'

        result[row['material'].id] = category

    return result


# =========================
def run_dss(product_id, source='operations'):
    from .models import BOM, Product, SalesData

    product = Product.objects.get(id=product_id)

    results = []

    boms = list(BOM.objects.filter(product=product))

    if not boms:
        print("NO BOM FOUND")
        return results

    # Deduplicate BOM rows by material for one product to avoid duplicate inventory rows
    material_bom_map = {}
    for bom in boms:
        if bom.material_id not in material_bom_map:
            material_bom_map[bom.material_id] = bom
        else:
            material_bom_map[bom.material_id].quantity_per_unit += bom.quantity_per_unit

    unique_boms = list(material_bom_map.values())

    # Use aggregated material demand with specified source
    material_stats = aggregate_material_demand(source=source)

    for bom in unique_boms:
        material = bom.material
        stats = material_stats.get(material.id, {"mean": 0.0, "variance": 0.0})

        material_mean = stats["mean"]
        material_std = np.sqrt(max(stats["variance"], 0.0))

        inv = inventory_analysis(material, material_mean, material_std)

        ip = inv['ip']
        rop = inv['rop']
        ss = inv['ss']

        demand = material_mean

        best_S, order_Q, min_cost = optimize_order_quantity(
            material,
            demand,
            ip,
            rop,
            ss
        )

        results.append({
            "material_id": material.source_id or f"NVL{material.id}",
            "material": material.name,
            "mean": round(material_mean, 2),
            "std": round(material_std, 2),
            "ip": round(ip, 2),
            "rop": round(rop, 2),
            "q": round(order_Q, 2),
            "ss": round(ss, 2),
            "s": round(best_S, 2),
            "cost": round(min_cost, 2),
        })

    return results


# =========================
# MPS (Master Planning Schedule) - PPA (Part Period Algorithm)
# =========================

def get_demand_by_product(product_id):
    """Lấy nhu cầu theo tháng.

    Hỗ trợ cả luồng Operations (Product.id) và Planning (product_code từ ProductRatio).
    """
    if str(product_id).isdigit():
        data = DisaggregatedPlan.objects.filter(product_id=product_id).order_by("month")
        if data.exists():
            return [int(x.qty) for x in data]

    product_code = str(product_id or "").strip()
    if not product_code:
        return []

    ratio_rows = ProductRatio.objects.filter(product_code=product_code).order_by("month")
    return [int(round(row.forecast_qty or 0)) for row in ratio_rows]


def get_orders_by_product(product_id):
    """Lấy đơn hàng khách hàng theo tháng (tháng 5-12).

    Với Planning hiện chưa có bảng đơn hàng riêng theo product_code, nên trả về 0.
    """
    if str(product_id).isdigit():
        orders = CustomerOrder.objects.filter(product_id=product_id).order_by("month")

        # map month → qty
        order_map = {o.month: o.qty for o in orders}

        result = []
        for m in range(5, 13):  # tháng 5 → 12
            result.append(order_map.get(m, 0))

        return result

    product_code = str(product_id or "").strip()
    if not product_code:
        return []

    ratio_count = ProductRatio.objects.filter(product_code=product_code).count()
    return [0] * ratio_count


def round_up(x, base=1000):
    """Làm tròn lên theo base (mặc định 1000)"""
    return int(math.ceil(x / base)) * base


def calculate_epp(C, H):
    """Tính Economic Part Period (EPP)"""
    return C / H


def ppa_lot_sizing(demand, C, H):
    """
    Phương pháp PPA (Part Period Algorithm) để xác định kích cỡ lô
    
    Tham số:
    - demand: list số lượng nhu cầu theo kỳ
    - C: chi phí thiết lập (setup cost)
    - H: chi phí lưu kho (holding cost)
    
    Trả về:
    - list kích cỡ lô
    """
    EPP = calculate_epp(C, H)

    n = len(demand)
    lots = [0] * n

    t = 0
    while t < n:
        start = t
        end = start
        current_pp = 0

        for i in range(start, n):
            Ri = demand[i]
            offset = i - start

            # Dừng khi part period mới vượt EPP.
            new_pp = current_pp + offset * Ri
            if new_pp > EPP:
                break

            current_pp = new_pp
            end = i

        lot_size = sum(demand[start:end + 1])
        lot_size = round_up(lot_size)

        lots[start] = lot_size
        t = end + 1

    return lots


def calculate_ppa_analysis(demand, C, H):
    """
    Tính chi tiết phân tích PPA
    
    Trả về:
    - ppa_details: list các bước PPA với chi tiết từng lô
    - lots: kích cỡ lô tối ưu
    """
    EPP = calculate_epp(C, H)
    n = len(demand)
    lots = [0] * n
    ppa_details = []
    ppa_steps = []  # flattened detailed rows for each k and i

    t = 0
    while t < n:
        start = t
        end = start
        current_pp = 0

        # accumulate months until adding next would exceed EPP
        for i in range(start, n):
            Ri = demand[i]
            offset = i - start

            # part period mới nếu thêm tháng này
            app = offset * Ri
            new_pp = current_pp + app
            if new_pp > EPP:
                break

            current_pp = new_pp
            end = i

        selected_demands = demand[start:end + 1]
        diff = abs(current_pp - EPP)

        ppa_details.append({
            'k': len(ppa_details) + 1,
            'periods': list(range(5 + start, 5 + end + 1)),  # Tháng 5-12
            'demands': selected_demands,
            'part_period': int(current_pp),
            'epp': int(EPP),
            'diff': int(diff),
            'selected': True
        })

        lot_size = sum(selected_demands)
        lot_size = round_up(lot_size)
        lots[start] = lot_size
        t = end + 1

    # PPA table rows follow the user's clarified boundary behavior:
    # when a row pushes APP(T) past EPP, keep that row, then immediately
    # restart the same demand index as a new lot row with the same k,
    # i=1, Ri unchanged, and APP(T)=0.
    current_i = 1
    for idx, ri in enumerate(demand):
        app = (current_i - 1) * ri

        ppa_steps.append({
            'k': idx + 1,
            'i': current_i,
            'Ri': ri,
            '(i-1)Ri': app,
            'APP(T)': app,
        })

        if app > EPP:
            ppa_steps.append({
                'k': idx + 1,
                'i': 1,
                'Ri': ri,
                '(i-1)Ri': 0,
                'APP(T)': 0,
            })
            current_i = 2
        else:
            current_i += 1

    return ppa_details, lots, ppa_steps


def calculate_mps(demand, orders, lots, begin_inventory=0):
    """
    Tính MPS (kế hoạch sản xuất) và ATP (Available To Promise)
    
    Tham số:
    - demand: nhu cầu dự báo theo kỳ
    - orders: đơn hàng khách hàng theo kỳ
    - lots: kích cỡ lô sản xuất (đã làm tròn)
    - begin_inventory: tồn kho ban đầu
    
    Trả về:
    - projected_on_hand: tồn kho dự báo
    - atp: Available To Promise
    - net_inventory: tồn kho trước MPS (= tồn kho trước kỳ - max(nhu cầu dự báo, đơn hàng KH))
    """
    n = len(demand)

    projected = [0] * n
    atp = [0] * n
    net_inventory = [0] * n

    for t in range(n):
        # Tính tồn kho trước MPS (net inventory)
        current_demand = demand[t] if t < len(demand) else 0
        current_orders = orders[t] if t < len(orders) else 0
        period_requirement = max(current_demand, current_orders)

        if t == 0:
            net_inventory[t] = begin_inventory - period_requirement
        else:
            net_inventory[t] = projected[t-1] - period_requirement

        # Tính tồn kho dự kiến = tồn kho trước MPS + cỡ lô
        projected[t] = net_inventory[t] + lots[t]

    # ATP
    for t in range(n):
        if lots[t] > 0:
            next_t = t + 1
            sum_orders = 0

            while next_t < n and lots[next_t] == 0:
                sum_orders += orders[next_t]
                next_t += 1

            if t == 0:
                atp[t] = lots[t] + begin_inventory - orders[t] - sum_orders
            else:
                atp[t] = lots[t] - orders[t] - sum_orders

    return projected, atp, net_inventory


def _normalize_receipts_schedule(receipts, horizon):
    normalized = [0.0] * horizon

    if not receipts:
        return normalized

    if isinstance(receipts, (int, float)):
        if horizon > 0:
            normalized[0] = float(receipts or 0)
        return normalized

    if isinstance(receipts, dict):
        receipts = [receipts]

    if isinstance(receipts, list):
        if receipts and all(not isinstance(item, dict) for item in receipts):
            for index, value in enumerate(receipts[:horizon]):
                try:
                    normalized[index] = float(value or 0)
                except (TypeError, ValueError):
                    normalized[index] = 0.0
            return normalized

        for entry in receipts:
            if not isinstance(entry, dict):
                continue

            period = entry.get('period', entry.get('month', entry.get('index')))
            quantity = entry.get('qty', entry.get('quantity', entry.get('value', 0)))

            try:
                period_index = int(period) - 1
            except (TypeError, ValueError):
                continue

            if 0 <= period_index < horizon:
                try:
                    normalized[period_index] += float(quantity or 0)
                except (TypeError, ValueError):
                    continue

    return normalized


def _lot_size_for_planning_item(item, required_quantity):
    required_quantity = float(required_quantity or 0)
    if required_quantity <= 0:
        return 0.0

    lot_policy = getattr(item, 'lot_policy', PlanningItem.LOT_POLICY_L4L)
    lot_size = float(getattr(item, 'lot_size', 0) or 0)

    if lot_policy == PlanningItem.LOT_POLICY_FOQ and lot_size > 0:
        return float(math.ceil(required_quantity / lot_size) * lot_size)

    if lot_policy == PlanningItem.LOT_POLICY_PPA and lot_size > 0:
        return float(math.ceil(required_quantity / lot_size) * lot_size)

    return required_quantity


def _build_planning_bom_graph(root_item_code):
    edges = list(
        MultiLevelBOMEdge.objects.all().order_by('root_product_code', 'level', 'parent_code', 'child_code')
    )

    adjacency = defaultdict(list)
    node_set = {root_item_code}

    for edge in edges:
        if edge.root_product_code != root_item_code and edge.parent_code != root_item_code:
            continue

        adjacency[edge.parent_code].append(edge)
        node_set.add(edge.parent_code)
        node_set.add(edge.child_code)

    reachable = set()
    stack = [root_item_code]
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        for edge in adjacency.get(current, []):
            stack.append(edge.child_code)

    adjacency = {
        parent_code: [edge for edge in children if edge.child_code in reachable]
        for parent_code, children in adjacency.items()
        if parent_code in reachable
    }

    indegree = {code: 0 for code in reachable}
    for parent_code, children in adjacency.items():
        for edge in children:
            indegree[edge.child_code] = indegree.get(edge.child_code, 0) + 1

    queue = [root_item_code]
    topo_order = []
    while queue:
        current = queue.pop(0)
        topo_order.append(current)
        for edge in adjacency.get(current, []):
            child_code = edge.child_code
            indegree[child_code] = indegree.get(child_code, 0) - 1
            if indegree[child_code] <= 0:
                queue.append(child_code)

    for code in reachable:
        if code not in topo_order:
            topo_order.append(code)

    return adjacency, topo_order


def _calculate_mrp_pre_columns(root_item_code):
    root_item_code = str(root_item_code or '').strip().upper()
    item_map = {
        item.item_code: item
        for item in PlanningItem.objects.all()
    }

    adjacency, topo_order = _build_planning_bom_graph(root_item_code)
    if root_item_code not in topo_order:
        topo_order.insert(0, root_item_code)

    root_lead_time = max(int(getattr(item_map.get(root_item_code), 'lead_time', 0) or 0), 0)
    semi_lead_time = 0
    material_lead_time = 0

    for item_code in topo_order:
        if item_code == root_item_code:
            continue

        item = item_map.get(item_code)
        if item is None:
            continue

        lead_time = max(int(getattr(item, 'lead_time', 0) or 0), 0)
        if item.item_type == PlanningItem.ITEM_TYPE_SEMI:
            semi_lead_time = max(semi_lead_time, lead_time)
        elif item.item_type == PlanningItem.ITEM_TYPE_MATERIAL:
            material_lead_time = max(material_lead_time, lead_time)

    return root_lead_time + semi_lead_time + material_lead_time


def calculate_mrp_plan(root_item_code, master_schedule, horizon=None, pre_columns=None):
    """Run a basic planning MRP explosion using PlanningItem and multi-level BOM data."""
    root_item_code = str(root_item_code or '').strip().upper()
    master_schedule = [float(value or 0) for value in (master_schedule or [])]
    if horizon is None:
        horizon = len(master_schedule)
    horizon = max(int(horizon or 0), len(master_schedule))
    pre_columns = max(int(pre_columns or 0), 0)
    total_horizon = horizon + pre_columns
    if horizon <= 0:
        horizon = len(master_schedule)

    if len(master_schedule) < horizon:
        master_schedule = master_schedule + [0.0] * (horizon - len(master_schedule))
    else:
        master_schedule = master_schedule[:horizon]

    master_schedule = [0.0] * pre_columns + master_schedule

    item_map = {
        item.item_code: item
        for item in PlanningItem.objects.all()
    }

    adjacency, topo_order = _build_planning_bom_graph(root_item_code)
    if root_item_code not in topo_order:
        topo_order.insert(0, root_item_code)

    gross_requirements_map = defaultdict(lambda: [0.0] * total_horizon)
    gross_requirements_map[root_item_code] = master_schedule[:]

    item_results = {}
    warnings = []

    for item_code in topo_order:
        item = item_map.get(item_code)
        if item is None:
            item = PlanningItem(
                item_code=item_code,
                item_name='',
                item_type=PlanningItem.ITEM_TYPE_PRODUCT if item_code == root_item_code else PlanningItem.ITEM_TYPE_MATERIAL,
                lead_time=0,
                on_hand=0,
                scheduled_receipts=[],
                lot_policy=PlanningItem.LOT_POLICY_L4L,
                lot_size=0,
                safety_stock=0,
            )
            warnings.append(f'Item {item_code} chưa có master item Planning, dùng mặc định.')

        gross = gross_requirements_map[item_code][:total_horizon]
        scheduled_receipts = _normalize_receipts_schedule(item.scheduled_receipts, total_horizon)
        lead_time = max(int(getattr(item, 'lead_time', 0) or 0), 0)
        on_hand = float(getattr(item, 'on_hand', 0) or 0)
        safety_stock = float(getattr(item, 'safety_stock', 0) or 0)

        projected = [0.0] * total_horizon
        net_requirements = [0.0] * total_horizon
        planned_order_receipts = [0.0] * total_horizon
        planned_order_releases = [0.0] * total_horizon
        past_due_release = 0.0

        available_previous = on_hand
        for index in range(total_horizon):
            gross_req = float(gross[index] or 0)
            scheduled_req = float(scheduled_receipts[index] or 0)
            available_before = available_previous + scheduled_req
            required_quantity = gross_req + safety_stock

            if available_before >= required_quantity:
                net_quantity = 0.0
                receipt_quantity = 0.0
                projected_available = available_before - gross_req
            else:
                net_quantity = max(required_quantity - available_before, 0.0)
                receipt_quantity = _lot_size_for_planning_item(item, net_quantity)
                projected_available = available_before + receipt_quantity - gross_req

            net_requirements[index] = round(net_quantity, 2)
            planned_order_receipts[index] = round(receipt_quantity, 2)
            projected[index] = round(projected_available, 2)
            available_previous = projected_available

        for index, receipt_quantity in enumerate(planned_order_receipts):
            if receipt_quantity <= 0:
                continue

            release_index = index - lead_time
            if release_index < 0:
                past_due_release += float(receipt_quantity or 0)
                release_index = 0

            planned_order_releases[release_index] += receipt_quantity

        item_results[item_code] = {
            'item_code': item_code,
            'item_name': item.item_name or item_code,
            'item_type': item.item_type,
            'lead_time': lead_time,
            'on_hand': round(on_hand, 2),
            'safety_stock': round(safety_stock, 2),
            'lot_policy': item.lot_policy,
            'lot_size': float(getattr(item, 'lot_size', 0) or 0),
            'gross_requirements': [round(value, 2) for value in gross],
            'scheduled_receipts': [round(value, 2) for value in scheduled_receipts],
            'projected_available': projected,
            'net_requirements': net_requirements,
            'planned_order_receipts': planned_order_receipts,
            'planned_order_releases': [round(value, 2) for value in planned_order_releases],
            'past_due_release': round(past_due_release, 2),
        }

        for edge in adjacency.get(item_code, []):
            child_code = edge.child_code
            child_gross = gross_requirements_map[child_code]
            for index in range(total_horizon):
                child_gross[index] += planned_order_releases[index] * float(edge.quantity_per_parent or 0)

    flat_rows = []
    for item_code in topo_order:
        if item_code in item_results:
            flat_rows.append(item_results[item_code])

    summary = {
        'root_item_code': root_item_code,
        'horizon': total_horizon,
        'forecast_horizon': horizon,
        'pre_columns': pre_columns,
        'item_count': len(flat_rows),
        'warnings': warnings,
        'missing_master_items': [row['item_code'] for row in flat_rows if row['item_code'] not in item_map],
    }

    return {
        'summary': summary,
        'items': flat_rows,
    }


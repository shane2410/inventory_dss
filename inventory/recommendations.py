import math
from collections import defaultdict

from .models import BOM, Material, Product
from .services import (
    abc_classification,
    forecast_product,
    inventory_analysis,
    optimize_order_quantity,
)


def _read_item_value(item, key, default=0):
    if isinstance(item, dict):
        if key in item:
            return item.get(key, default)
        return item.get(key.lower(), default)

    if hasattr(item, key):
        return getattr(item, key)

    return getattr(item, key.lower(), default)


def generate_recommendation(item):
    """
    Generate decision + JSON payload from inventory indicators and ABC class.

    Required fields in item (dict/object):
    - item / item_code
    - IP
    - ROP
    - S
    - ABC_class
    - avg_daily_demand (optional)
    """
    item_code = str(
        _read_item_value(item, "item", _read_item_value(item, "item_code", "UNKNOWN"))
    )
    ip = float(_read_item_value(item, "IP", 0) or 0)
    rop = float(_read_item_value(item, "ROP", 0) or 0)
    target_stock = float(_read_item_value(item, "S", ip) or ip)
    abc_class = str(_read_item_value(item, "ABC_class", "B") or "B").upper()
    avg_daily_demand = float(_read_item_value(item, "avg_daily_demand", 0) or 0)

    should_order = ip <= rop
    action = "ORDER" if should_order else "NO_ORDER"
    order_qty = max(target_stock - ip, 0) if should_order else 0

    urgency = {
        "A": "URGENT",
        "B": "MEDIUM",
        "C": "LOW",
    }.get(abc_class, "LOW") if should_order else "LOW"

    if action == "ORDER":
        if urgency == "URGENT":
            recommendation = "Đặt hàng ngay"
        elif urgency == "MEDIUM":
            recommendation = "Đặt hàng sớm"
        else:
            recommendation = "Cân nhắc đặt hàng theo chu kỳ"
    else:
        recommendation = "Theo dõi thêm"

    if action == "ORDER" and avg_daily_demand > 0:
        days_left = max(ip / avg_daily_demand, 0)
        message = f"Tồn kho sắp hết trong {math.ceil(days_left)} ngày, cần đặt ngay"
    elif action == "ORDER":
        message = "Cần đặt bổ sung tồn kho theo mức an toàn"
    else:
        message = "Tồn kho an toàn, tiếp tục theo dõi"

    payload = {
        "item": item_code,
        "action": action,
        "quantity": int(round(order_qty)),
        "urgency": urgency,
        "message": message,
    }

    decision = {
        "action": action,
        "order_qty": round(order_qty, 2),
        "urgency": urgency,
        "recommendation": recommendation,
        "message": message,
        "json": payload,
    }

    return decision


def build_inventory_alert_recommendations():
    """
    Build a shared alert-oriented material list.

    This follows the alert page logic (ip < rop) and maps the resulting
    materials directly to ABC-based urgency tiers.
    """
    demand_stats = defaultdict(lambda: {"mean": 0.0, "variance": 0.0})

    for product in Product.objects.all():
        mean, std, _, _, _, _ = forecast_product(product.id)
        mean = max(float(mean or 0), 0.0)
        std = max(float(std or 0), 0.0)

        for bom in BOM.objects.filter(product=product).select_related("material"):
            qty = float(bom.quantity_per_unit or 0)
            if qty <= 0:
                continue

            demand_stats[bom.material_id]["mean"] += mean * qty
            demand_stats[bom.material_id]["variance"] += (std * qty) ** 2

    materials = list(Material.objects.all())
    abc_input = [
        {
            "material": material,
            "demand": demand_stats[material.id]["mean"],
        }
        for material in materials
    ]
    abc_map = abc_classification(abc_input)

    alerts = []

    for product in Product.objects.all():
        mean, std, _, _, _, _ = forecast_product(product.id)

        for bom in BOM.objects.filter(product=product).select_related("material"):
            material = bom.material

            demand = mean * bom.quantity_per_unit
            ip = material.on_hand + material.on_order
            lead_time = max(material.leadtime, 1)
            z = 1.65
            material_std = std * bom.quantity_per_unit
            ss = z * material_std * (lead_time ** 0.5)
            rop = demand * lead_time + ss

            if ip < rop:
                abc_class = abc_map.get(material.id, "C")
                urgency = {
                    "A": "URGENT",
                    "B": "MEDIUM",
                    "C": "LOW",
                }.get(abc_class, "LOW")

                item_code = material.source_id or f"NVL{material.id}"

                S, Q, cost = optimize_order_quantity(material, demand, ip, rop, ss)

                days_left = None
                if demand > 0:
                    days_left = math.ceil(ip / demand)

                if days_left is not None:
                    message = f"Tồn kho sắp hết trong {days_left} ngày, cần đặt ngay"
                else:
                    message = "Cần đặt bổ sung tồn kho theo mức an toàn"

                alerts.append({
                    "item": item_code,
                    "product": product.name,
                    "material_code": material.source_id or f"NVL{material.id}",
                    "material_name": material.name,
                    "ip": round(ip, 2),
                    "rop": round(rop, 2),
                    "ss": round(ss, 2),
                    "status": "ORDER",
                    "s": round(S, 2),
                    "q": round(Q, 2),
                    "cost": round(cost, 2),
                    "urgency": urgency,
                    "action": "ORDER",
                    "recommendation": "Đặt hàng ngay" if urgency == "URGENT" else ("Đặt hàng sớm" if urgency == "MEDIUM" else "Cân nhắc đặt hàng theo chu kỳ"),
                    "message": message,
                    "days_left": days_left,
                    "abc_class": abc_class,
                })

    alerts.sort(key=lambda x: (0 if x["urgency"] == "URGENT" else 1 if x["urgency"] == "MEDIUM" else 2, x["material_name"]))

    summary = {
        "urgent": sum(1 for item in alerts if item["urgency"] == "URGENT"),
        "medium": sum(1 for item in alerts if item["urgency"] == "MEDIUM"),
        "low": sum(1 for item in alerts if item["urgency"] == "LOW"),
        "order": len(alerts),
        "safe": max(Material.objects.count() - len(alerts), 0),
    }

    return alerts, summary


def build_dashboard_recommendations(limit=8):
    alerts, summary = build_inventory_alert_recommendations()
    items = []

    for alert in alerts:
        if alert["urgency"] != "URGENT":
            continue

        items.append({
            "item": alert["item"],
            "material_name": alert["material_name"],
            "abc_class": alert.get("abc_class") or "C",
            "action": alert["action"],
            "urgency": alert["urgency"],
            "recommendation": alert["recommendation"],
            "message": alert["message"],
            "quantity": alert["q"],
            "ip": alert["ip"],
            "rop": alert["rop"],
            "s": alert["s"],
            "ss": alert["ss"],
            "mean_demand": 0,
            "estimated_cost": alert["cost"],
            "json": {
                "item": alert["item"],
                "action": alert["action"],
                "quantity": int(round(alert["q"])),
                "urgency": alert["urgency"],
                "message": alert["message"],
            },
        })

    return items, summary

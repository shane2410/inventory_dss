import math
import os
from collections import defaultdict

from .models import BOM, Material, Product
from .services import (
    abc_classification,
    aggregate_material_demand,
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

    should_order = ip < rop
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
        # Days of Supply (DoS) = I_OH / D_avg (on-hand inventory only)
        ioh = _read_item_value(item, "IOH", _read_item_value(item, "on_hand", 0))
        ioh = float(ioh) if ioh is not None else 0
        days_left = max(ioh / avg_daily_demand, 0) if ioh > 0 else 0
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


def build_inventory_alert_recommendations(source='operations'):
    """
    Build a shared alert-oriented material list.

    This follows the alert page logic (ip < rop) and maps the resulting
    materials directly to ABC-based urgency tiers.
    """
    demand_stats = aggregate_material_demand(source=source)

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

    for material in materials:
        demand = demand_stats[material.id]["mean"]
        variance = demand_stats[material.id]["variance"]

        material_std = math.sqrt(max(variance, 0.0))
        inv = inventory_analysis(material, demand, material_std)
        ip = inv["ip"]
        ss = inv["ss"]
        rop = inv["rop"]

        if ip >= rop:
            continue

        # compute Days of Supply (DoS) and Lead Time (L)
        abc_class = abc_map.get(material.id, "C")
        days_left_float = None
        days_left = None
        if demand > 0:
            # Days of Supply (DoS) = I_OH / D_avg
            ioh = float(getattr(material, 'on_hand', 0) or 0)
            days_left_float = ioh / demand
            days_left = math.ceil(days_left_float) if days_left_float > 0 else 0

        leadtime = getattr(material, "leadtime", None)

        # Urgency index (I_UT) = DoS / LeadTime
        iut = None
        if days_left_float is not None and leadtime and leadtime > 0:
            iut = days_left_float / float(leadtime)

        # Map CR/I_UT to urgency tiers (conservative fallback if I_UT unknown)
        if iut is None:
            urgency = "URGENT"
        else:
            if iut < 0.9:
                urgency = "URGENT"
            elif iut <= 1.1:
                urgency = "MEDIUM"
            else:
                urgency = "LOW"

        item_code = material.source_id or f"NVL{material.id}"

        S, Q, cost = optimize_order_quantity(material, demand, ip, rop, ss)

        # reuse values computed above
        if days_left is not None:
            message = f"Tồn kho sắp hết trong {days_left} ngày, cần đặt ngay"
        else:
            message = "Cần đặt bổ sung tồn kho theo mức an toàn"

        alerts.append({
            "item": item_code,
            "product": None,
            "material_code": item_code,
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
            "days_left_float": days_left_float,
            "leadtime": leadtime,
            "iut": round(iut, 3) if iut is not None else None,
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


def build_inventory_watchlist_recommendations(source='operations'):
    """
    Build a watchlist of materials in stable status that are approaching ROP threshold.
    
    Watchlist condition: ROP < IP <= ROP * 1.1 (stable, recently recovered from low stock)
    """
    demand_stats = aggregate_material_demand(source=source)

    materials = list(Material.objects.all())
    abc_input = [
        {
            "material": material,
            "demand": demand_stats[material.id]["mean"],
        }
        for material in materials
    ]
    abc_map = abc_classification(abc_input)

    watchlist = []

    for material in materials:
        demand = demand_stats[material.id]["mean"]
        variance = demand_stats[material.id]["variance"]

        material_std = math.sqrt(max(variance, 0.0))
        inv = inventory_analysis(material, demand, material_std)
        ip = inv["ip"]
        ss = inv["ss"]
        rop = inv["rop"]

        # Watchlist: ROP < IP <= ROP * 1.1 (stable status, just above ROP)
        if not (rop < ip <= rop * 1.1):
            continue

        abc_class = abc_map.get(material.id, "C")
        days_left_float = None
        days_left = None
        if demand > 0:
            # Days of Supply (DoS) = I_OH / D_avg
            ioh = float(getattr(material, 'on_hand', 0) or 0)
            days_left_float = ioh / demand
            days_left = math.ceil(days_left_float) if days_left_float > 0 else 0

        leadtime = getattr(material, "leadtime", None)

        # Urgency index (I_UT) = DoS / LeadTime
        iut = None
        if days_left_float is not None and leadtime and leadtime > 0:
            iut = days_left_float / float(leadtime)

        # Map CR/I_UT to urgency tiers
        if iut is None:
            urgency = "MEDIUM"  # Watchlist items are cautionary
        else:
            if iut < 0.9:
                urgency = "URGENT"
            elif iut <= 1.1:
                urgency = "MEDIUM"
            else:
                urgency = "LOW"

        item_code = material.source_id or f"NVL{material.id}"

        S, Q, cost = optimize_order_quantity(material, demand, ip, rop, ss)

        if days_left is not None:
            message = f"Sắp chạm ngưỡng trong {days_left} ngày"
        else:
            message = "Vật tư sắp chạm ngưỡng đặt hàng"

        watchlist.append({
            "item": item_code,
            "product": None,
            "material_code": item_code,
            "material_name": material.name,
            "ip": round(ip, 2),
            "rop": round(rop, 2),
            "ss": round(ss, 2),
            "status": "WATCH",
            "s": round(S, 2),
            "q": round(Q, 2),
            "cost": round(cost, 2),
            "urgency": urgency,
            "action": "MONITOR",
            "recommendation": "Theo dõi kỹ" if urgency != "LOW" else "Cân nhắc đặt hàng",
            "message": message,
            "days_left": days_left,
            "days_left_float": days_left_float,
            "leadtime": leadtime,
            "iut": round(iut, 3) if iut is not None else None,
            "abc_class": abc_class,
        })

    watchlist.sort(key=lambda x: -x["ip"])  # Sort by IP descending (closest to 110% ROP first)

    return watchlist


def build_dashboard_recommendations(limit=8, source='operations'):
    alerts, summary = build_inventory_alert_recommendations(source=source)
    items = []

    for alert in alerts:
        if alert["urgency"] != "URGENT":
            continue

        items.append({
            "item": alert["item"],
            "material_name": alert["material_name"],
            "leadtime": alert.get("leadtime"),
            "iut": alert.get("iut"),
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

    return items[:limit], summary

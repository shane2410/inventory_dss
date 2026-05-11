from django.db import models
from datetime import date


# =========================
# MATERIAL
# =========================
class Material(models.Model):
    source_id = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    on_hand= models.FloatField(default=0)

    # Inventory
    on_order = models.IntegerField(default=0)

    # Lead time
    leadtime = models.IntegerField(default=1)

    # Cost
    holding_cost = models.FloatField(help_text="Chi phí lưu kho (h)")
    ordering_cost = models.FloatField(help_text="Chi phí đặt hàng (K)")
    price_cost = models.FloatField(help_text="Giá vật tư (P)")

    def __str__(self):
        return self.name


# =========================
# PRODUCT
# =========================
class Product(models.Model):
    source_id = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# =========================
# BOM (Bill of Materials)
# =========================
class BOM(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantity_per_unit = models.FloatField()

    def __str__(self):
        return f"{self.product} - {self.material}"


class MultiLevelBOMEdge(models.Model):
    TYPE_PRODUCT = "PRODUCT"
    TYPE_SEMI = "SEMI"
    TYPE_MATERIAL = "MATERIAL"

    NODE_TYPE_CHOICES = (
        (TYPE_PRODUCT, "Product"),
        (TYPE_SEMI, "Semi-finished"),
        (TYPE_MATERIAL, "Material"),
    )

    root_product_code = models.CharField(max_length=64, db_index=True)
    parent_code = models.CharField(max_length=64, db_index=True)
    parent_type = models.CharField(max_length=16, choices=NODE_TYPE_CHOICES)
    child_code = models.CharField(max_length=64, db_index=True)
    child_type = models.CharField(max_length=16, choices=NODE_TYPE_CHOICES)
    quantity_per_parent = models.FloatField()
    level = models.PositiveIntegerField(default=0)
    remark = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["root_product_code", "parent_code", "child_code"],
                name="uniq_multilevel_bom_edge",
            )
        ]
        ordering = ["root_product_code", "level", "parent_code", "child_code"]

    def __str__(self):
        return f"{self.root_product_code}: {self.parent_code} -> {self.child_code}"


# =========================
# SALES DATA (Demand)
# =========================
class SalesData(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    date = models.DateField(default=date.today)  # 👉 FIX quan trọng
    quantity = models.IntegerField()

    def __str__(self):
        return f"{self.product} - {self.date}"


# =========================
# TRANSACTION
# =========================
class Transaction(models.Model):
    TRANSACTION_TYPE = (
        ('IN', 'Nhập kho'),
        ('OUT', 'Xuất kho'),
    )

    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    transaction_type = models.CharField(max_length=3, choices=TRANSACTION_TYPE)
    date = models.DateField()

    def __str__(self):
        return f"{self.material} - {self.transaction_type} - {self.quantity}"
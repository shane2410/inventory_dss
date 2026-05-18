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


class ProductRatio(models.Model):
    product_code = models.CharField(max_length=50, db_index=True, default='', blank=True)
    product_name = models.CharField(max_length=255, default='', blank=True)
    month = models.DateField(db_index=True)
    ratio = models.FloatField(default=0)
    forecast_qty = models.FloatField(default=0)

    class Meta:
        unique_together = ('product_code', 'month')
        ordering = ['month', 'product_code']

    def __str__(self):
        return f"{self.product_code} - {self.product_name} - {self.month:%m/%Y}"


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
    SOURCE_OPERATIONS = 'operations'
    SOURCE_PLANNING = 'planning'
    SOURCE_CHOICES = (
        (SOURCE_OPERATIONS, 'Operations'),
        (SOURCE_PLANNING, 'Planning'),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    date = models.DateField(default=date.today)  # 👉 FIX quan trọng
    quantity = models.IntegerField()
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_OPERATIONS,
        db_index=True,
    )

    def __str__(self):
        return f"{self.product} - {self.date} ({self.source})"


# =========================
# TRANSACTION
# =========================
class Transaction(models.Model):
    SOURCE_OPERATIONS = 'operations'
    SOURCE_PLANNING = 'planning'
    SOURCE_CHOICES = (
        (SOURCE_OPERATIONS, 'Operations'),
        (SOURCE_PLANNING, 'Planning'),
    )
    
    TRANSACTION_TYPE = (
        ('IN', 'Nhập kho'),
        ('OUT', 'Xuất kho'),
    )

    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    transaction_type = models.CharField(max_length=3, choices=TRANSACTION_TYPE)
    date = models.DateField()
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_OPERATIONS,
        db_index=True,
    )

    def __str__(self):
        return f"{self.material} - {self.transaction_type} - {self.quantity} ({self.source})"


# =========================
# MONTHLY PRODUCTION HISTORY
# =========================
class MonthlyProductionData(models.Model):
    SOURCE_PLANNING = 'planning'
    SOURCE_CHOICES = (
        (SOURCE_PLANNING, 'Planning'),
    )

    month = models.DateField(db_index=True)
    quantity = models.FloatField()
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_PLANNING,
        db_index=True,
    )

    class Meta:
        ordering = ['month']
        unique_together = ('month', 'source')

    def __str__(self):
        return f"{self.month:%m/%Y} - {self.quantity} ({self.source})"


class PlanningConfiguration(models.Model):
    """Lưu các input parameters cho kế hoạch tổng hợp"""
    opening_inventory = models.FloatField(default=0)
    workers = models.IntegerField(default=50)
    productivity = models.FloatField(default=150)
    regular_cost = models.FloatField(default=0)
    overtime_cost = models.FloatField(default=0)
    subcontract_cost = models.FloatField(default=0)
    inventory_cost = models.FloatField(default=0)
    backorder_cost = models.FloatField(default=0)
    ot_limit_pct = models.FloatField(default=20)
    inventory_policy = models.FloatField(default=0)
    current_workers = models.IntegerField(default=50)
    hire_cost = models.FloatField(default=0)
    layoff_cost = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Planning Configurations"

    def __str__(self):
        return f"Planning Config - {self.updated_at:%Y-%m-%d %H:%M}"


# =========================
# DISAGGREGATED PLAN (Phân rã theo sản phẩm)
# =========================
class DisaggregatedPlan(models.Model):
    """Sản lượng đã phân rã theo loại sản phẩm"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    month = models.IntegerField()
    qty = models.IntegerField()

    class Meta:
        ordering = ['month']
        unique_together = ('product', 'month')

    def __str__(self):
        return f"{self.product} - Tháng {self.month} - Qty: {self.qty}"


# =========================
# CUSTOMER ORDER
# =========================
class CustomerOrder(models.Model):
    """Đơn hàng khách hàng"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    month = models.IntegerField()
    qty = models.IntegerField()

    class Meta:
        ordering = ['month']

    def __str__(self):
        return f"{self.product} - Tháng {self.month} - Qty: {self.qty}"


# =========================
# MPS CONFIGURATION (Thiết lập tham số cho MPS)
# =========================
class MPSConfiguration(models.Model):
    """Lưu các input parameters cho MPS"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    setup_cost = models.FloatField(default=40000000, help_text="Chi phí thiết lập (C)")
    holding_cost = models.FloatField(default=250, help_text="Chi phí lưu kho (H)")
    begin_inventory = models.FloatField(default=0, help_text="Tồn kho ban đầu")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "MPS Configurations"

    def __str__(self):
        if self.product:
            return f"MPS Config - {self.product}"
        return f"MPS Config - {self.updated_at:%Y-%m-%d}"


# =========================
# SELECTED PRODUCT FOR MPS (Danh sách sản phẩm được chọn ở trang Phân rã)
# =========================
class SelectedProductForMPS(models.Model):
    """Lưu lịch sử các sản phẩm (ID_P) được chọn tại trang Phân rã sản phẩm"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    selected_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-selected_at']
        unique_together = ('product',)  # Mỗi sản phẩm chỉ lưu 1 lần

    def __str__(self):
        return f"{self.product} - Chọn lúc: {self.selected_at:%Y-%m-%d %H:%M}"
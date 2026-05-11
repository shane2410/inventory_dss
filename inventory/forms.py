from django import forms
from .models import Material, Transaction

class ImportDataForm(forms.Form):
    IMPORT_TYPE_CHOICES = (
        ('sales', 'Dữ liệu bán hàng (SalesData)'),
        ('transaction', 'Dữ liệu giao dịch (Transaction)'),
    )
    
    import_type = forms.ChoiceField(
        choices=IMPORT_TYPE_CHOICES,
        widget=forms.RadioSelect,
        label='Loại dữ liệu'
    )
    file = forms.FileField(
        label='Chọn file Excel (.xlsx)',
        widget=forms.FileInput(attrs={'accept': '.xlsx'})
    )


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['source_id', 'name', 'price_cost', 'ordering_cost', 'holding_cost', 'leadtime', 'on_hand', 'on_order']
        widgets = {
            'source_id': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'price_cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'ordering_cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'holding_cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'leadtime': forms.NumberInput(attrs={'class': 'form-control'}),
            'on_hand': forms.NumberInput(attrs={'class': 'form-control'}),
            'on_order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['material', 'quantity', 'transaction_type', 'date']
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


class MultiLevelBOMEntryForm(forms.Form):
    NODE_TYPE_CHOICES = (
        ("PRODUCT", "Product"),
        ("SEMI", "Semi-finished"),
        ("MATERIAL", "Material"),
    )

    root_product_code = forms.CharField(max_length=64, label="Mã sản phẩm gốc")
    parent_code = forms.CharField(max_length=64, label="Mã cha")
    parent_type = forms.ChoiceField(choices=NODE_TYPE_CHOICES, label="Loại cha")
    child_code = forms.CharField(max_length=64, label="Mã con")
    child_type = forms.ChoiceField(choices=NODE_TYPE_CHOICES, label="Loại con")
    quantity_per_parent = forms.FloatField(
        min_value=1,
        label="Số lượng cho mỗi cha",
        widget=forms.NumberInput(attrs={"step": "1", "min": "1"}),
    )
    level = forms.IntegerField(min_value=0, initial=0, label="Cấp")
    remark = forms.CharField(max_length=255, required=False, label="Ghi chú")

    def _validate_prefix(self, code, node_type, field_name):
        code_text = str(code or "").strip().upper()

        if node_type == "PRODUCT" and not code_text.startswith("P"):
            self.add_error(field_name, "Mã Product phải bắt đầu bằng 'P'.")
        if node_type == "MATERIAL" and not code_text.startswith("RM"):
            self.add_error(field_name, "Mã Material phải bắt đầu bằng 'RM'.")

    def clean(self):
        cleaned = super().clean()

        root_product_code = str(cleaned.get("root_product_code") or "").strip()
        parent_code = str(cleaned.get("parent_code") or "").strip()
        child_code = str(cleaned.get("child_code") or "").strip()
        parent_type = cleaned.get("parent_type")
        child_type = cleaned.get("child_type")

        if root_product_code and not root_product_code.upper().startswith("P"):
            self.add_error("root_product_code", "Mã sản phẩm gốc phải bắt đầu bằng 'P'.")

        if parent_code and child_code and parent_code.upper() == child_code.upper():
            self.add_error("child_code", "Mã con không được trùng mã cha.")

        if parent_code and parent_type:
            self._validate_prefix(parent_code, parent_type, "parent_code")

        if child_code and child_type:
            self._validate_prefix(child_code, child_type, "child_code")

        cleaned["root_product_code"] = root_product_code.upper()
        cleaned["parent_code"] = parent_code.upper()
        cleaned["child_code"] = child_code.upper()

        return cleaned
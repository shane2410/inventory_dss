from django import forms
from .models import Material, PlanningItem, Transaction


class MonthlyForecastImportForm(forms.Form):
    file = forms.FileField(
        label='Chọn file Excel (.xlsx)',
        widget=forms.FileInput(attrs={'accept': '.xlsx'})
    )

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


class PlanningItemForm(forms.ModelForm):
    class Meta:
        model = PlanningItem
        fields = [
            'item_code',
            'item_name',
            'item_type',
            'lead_time',
            'on_hand',
            'scheduled_receipts',
            'lot_policy',
            'lot_size',
            'safety_stock',
            'remark',
        ]
        widgets = {
            'item_code': forms.TextInput(attrs={'class': 'form-control'}),
            'item_name': forms.TextInput(attrs={'class': 'form-control'}),
            'item_type': forms.Select(attrs={'class': 'form-control'}),
            'lead_time': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'on_hand': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'scheduled_receipts': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'lot_policy': forms.Select(attrs={'class': 'form-control'}),
            'lot_size': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'safety_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'remark': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_scheduled_receipts(self):
        value = self.cleaned_data.get('scheduled_receipts')
        if value in (None, ''):
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []

            import json

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise forms.ValidationError('scheduled_receipts phải là JSON hợp lệ.') from exc

            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]

            raise forms.ValidationError('scheduled_receipts phải là JSON object hoặc JSON array.')

        return value
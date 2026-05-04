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
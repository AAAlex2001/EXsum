from django import forms
from .models import IncomeExpense, ContractorDebtOperation
from catalog.models import Bill,Category, Contractor, CashFlow, Currency


class BulkUpdateForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label="---",
        label="Новая категория",
        widget=forms.Select(attrs={
            "class": "block w-full rounded-lg border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2"
        })
    )
    contractor = forms.ModelChoiceField(
        queryset=Contractor.objects.all(),
        required=False,
        empty_label="---",
        label="Новый контрагент",
        widget=forms.Select(attrs={
            "class": "block w-full rounded-lg border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2"
        })
    )
    cashflow = forms.ModelChoiceField(
        queryset=CashFlow.objects.all(),
        required=False,
        empty_label="---",
        label="Новый ДДС",
        widget=forms.Select(attrs={
            "class": "block w-full rounded-lg border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2"
        })
    )

class IncomeExpenseForm(forms.ModelForm):
    class Meta:
        model = IncomeExpense
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['income_account'].disabled = True
            self.fields['expense_account'].disabled = True


class ContractorDebtOperationForm(forms.ModelForm):
    class Meta:
        model = ContractorDebtOperation
        fields = '__all__'  # или перечислить ['contractor','amount','percent','currency','comment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['currency'].queryset = Currency.objects.exclude(
            short_name='USD')

        # Заблокировать поля для существующих записей
        if self.instance and self.instance.pk:
            self.fields['contractor'].disabled = True
            self.fields['deal'].disabled = True

        # Убрать карандаш/глаз/плюс
        if 'contractor' in self.fields:
            self.fields['contractor'].widget.can_add_related = False
            self.fields['contractor'].widget.can_change_related = False
            self.fields['contractor'].widget.can_view_related = False
            self.fields['contractor'].widget.can_delete_related = False

        if 'currency' in self.fields:
            self.fields['currency'].widget.can_add_related = False
            self.fields['currency'].widget.can_change_related = False
            self.fields['currency'].widget.can_view_related = False
            self.fields['currency'].widget.can_delete_related = False




class IncomeExpenseFormV2(forms.ModelForm):
    class Meta:
        model = IncomeExpense
        fields = '__all__'
        widgets = {
            'income_account': forms.Select(),  # не задаем choices на уровне Meta
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Теперь запрос выполняется во время создания формы, а не при импорте модуля.
        bill_choices = [('', 'Выберите счет')] + list(Bill.objects.values_list('id', 'name'))
        self.fields['income_account'].widget.choices = bill_choices
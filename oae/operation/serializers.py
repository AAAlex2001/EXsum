from rest_framework import serializers
from .models import IncomeExpense
from decimal import Decimal, ROUND_HALF_UP

class IncomeExpenseSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()
    cashflow = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    deal_id = serializers.SerializerMethodField()

    def get_deal_id(self, obj):
        try:
            return obj.deal.id
        except Exception as e:
            return {'error': str(e)}

    def get_cashflow(self, obj):
        try:
            if obj.deal.cashflow:
                return obj.deal.cashflow.name
            else:
                return ""
        except Exception as e:
            return {'error': str(e)}

    def get_category(self, obj):
        try:
            if obj.deal.category:
                return obj.deal.category.name
            else:
                return ""
        except Exception as e:
            return {'error': str(e)}

    def get_amount(self, obj):
        try:
            if obj.deal.national_currency and obj.deal.national_currency != 0:
                return obj.deal.national_currency
            if obj.income_account:
                if obj.income_account.currency.short_name not in ['USD', 'USDT']:
                    return obj.income_amount.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

            return None
        except Exception as e:
            return {'error': str(e)}

    class Meta:
        model = IncomeExpense
        fields = ['id', 'date_create', 'date_update', 'amount', 'cashflow', 'category', 'deal_id']
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from django.utils.dateparse import parse_datetime
from .models import IncomeExpense
from .serializers import IncomeExpenseSerializer
from django.db.models import Q
from rest_framework.response import Response

class IncomeExpenseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IncomeExpense.objects.filter(Q(deal__contractor__id=1) | Q(deal__cashflow__id__in=[7,9]) | Q(deal__category__id__in=[2,4])).order_by('-date_create')
    serializer_class = IncomeExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if date_from:
            qs = qs.filter(date_create__gte=parse_datetime(date_from))
        if date_to:
            qs = qs.filter(date_create__lte=parse_datetime(date_to))

        return qs


class CheckAutocomplete(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        from catalog.models import Bill
        category_name = request.GET.get('category', '')
        if category_name == 'Сделка с клиентом':
            expense_accounts = Bill.objects.filter(id=8).values('id', 'name')
            income_accounts = Bill.objects.exclude(id=8).values('id', 'name')          
            required_fields = ['income_amount', 'expense_amount']
            data = {'income_accounts': income_accounts, 'expense_accounts': expense_accounts, 'required_fields': required_fields}
            return Response(data, status=200)
        elif category_name == 'Сделка с КК':
            contractor = {'name': 'ИП', 'id': 1}
            cashflow = {'name': 'Взаимозачёт', 'id': 9}
            required_fields = ['income_amount', 'income_account', 'If USD in income_account name, than national_currency required']
            data = {'contractor': contractor, 'cashflow': cashflow, 'required_fields': required_fields}
            return Response(data, status=200)
        return Response({'detail': 'No data'}, status=400)


class CheckNationalCurrency(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        from catalog.models import Bill
        bill_id = request.GET.get('bill_id', False)
        if bill_id:
            bill = Bill.objects.get(id=int(bill_id))
            if 'USD' in bill.currency.short_name:
                return Response({'required_national_currency': True}, status=200)
            else:
                return Response({'required_national_currency': False}, status=200)
        bill_name = request.GET.get('bill_name', False)
        if bill_name:
            bill = Bill.objects.get(short_name=bill_name)
            if 'USD' in bill.currency.short_name:
                return Response({'required_national_currency': True}, status=200)
            else:
                return Response({'required_national_currency': False}, status=200)
        return Response({'detail': 'No data'}, status=400)


class GetCashflowBalance(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from catalog.models import Contractor, ContractorHistory
        contractor_id = request.GET.get('contractor_id', False)
        contractor = Contractor.objects.get(id=int(contractor_id))
        if ContractorHistory.objects.filter(contractor=contractor).count() != 0:
            contractor_bill = ContractorHistory.objects.filter(contractor=contractor).last()
            balance_cost = contractor_bill.duty
            if balance_cost == 0:
                balance_cost = int(0)
            balance_usdt = contractor_bill.duty_usdt
            if balance_usdt == 0:
                balance_usdt = int(0)
        else:
            balance_cost = contractor.duty
            balance_usdt = contractor.duty_usdt
            if balance_cost == 0:
                balance_cost = int(0)
            if balance_usdt == 0:
                balance_usdt = int(0)
        return Response({'cashflow_bill': "{0}Р / {1}$".format(str(balance_cost), str(balance_usdt))}, status=200)
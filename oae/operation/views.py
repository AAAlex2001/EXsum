from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from django.utils.dateparse import parse_datetime
from catalog.models import Contractor, Category, CashFlow, Bill
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
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
            #income_account = {'name': 'USDT ОАЭ', 'id': 8}
            expense_accounts = Bill.objects.all().values('id', 'name')  #filter(id__in=[8,22,24,30,31,32])
            #expense_accounts = Bill.objects.exclude(id=8).values('id', 'name')
            income_accounts = Bill.objects.all().values('id', 'name') #
            required_fields = ['income_amount', 'expense_amount']
            #data = {'income_account': income_account, 'expense_accounts': expense_accounts, 'required_fields': required_fields}
            data = {'income_accounts': income_accounts, 'expense_accounts': expense_accounts, 'required_fields': required_fields}
            return Response(data, status=200)
        elif category_name == 'Сделка с КК':
            #contractor = {'name': 'ИП', 'id': 1}
            contractors = Contractor.objects.all()#filter(id__in=[1])
            contractor_data = []
            for contractor in contractors:
                contractor_data.append({'id': contractor.id, 'name': contractor.name})
            #cashflow = {'name': 'Взаимозачёт', 'id': 9}
            cashflows = CashFlow.objects.all()#filter(id__in=[23,24])
            cashflow_data = []
            for cashflow in cashflows:
                cashflow_data.append({'name': cashflow.name, 'id': cashflow.id})
            #cashflow = [{'name': 'Взаимозачёт', 'id': 9}, {'name': 'test', 'id': 11}]
            required_fields = ['income_amount', 'income_account', 'If USD in income_account name, than national_currency required']
            data = {'contractor': contractor_data, 'cashflow': cashflow_data, 'required_fields': required_fields}
            return Response(data, status=200)
        return Response({'detail': 'No data'}, status=400)


class GetRateInfo(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        import requests
        from .models import PercentCourse, CourseHistory
        from catalog.models import Currency
        from django.contrib.auth import get_user_model
        from decimal import Decimal, ROUND_HALF_UP
        User = get_user_model()
        user_id = request.GET.get('user_id', False)
        if not user_id:
            return Response({'error': "Не указан id пользователя"}, status=200)
        users = User.objects.filter(id=int(user_id))
        if users.count() == 0:
            return Response({'error': "Пользователя не существует"}, status=200)
        user = users.first()
        direction = ''
        variation = ''
        errors_list = []
        try:
            url = 'https://api.rapira.net/open/market/rates'
            r = requests.get(url, timeout=2)
            r.raise_for_status()
            data = r.json()
            course_percent = PercentCourse.objects.first().value
            course_main = Decimal(data['data'][0]['close'])
            try:
                course_hist = CourseHistory.objects.get(currency__short_name='USDT')
                old_course = Decimal(course_hist.new_value)
                new_course = Decimal(course_main)
                """if new_course > old_course:
                    direction = 'up'
                    variation = (new_course - old_course) / old_course * 100
                else:
                    direction = 'down'
                    variation = (new_course - old_course) / old_course * 100"""
                if old_course != 0:
                    variation = ((new_course - old_course) / old_course) * 100
                    direction = 'up' if new_course > old_course else 'down'
                else:
                    variation = 0
                    direction = 'up'
                course_hist.old_value = float(old_course)
                course_hist.new_value = float(new_course)
                course_hist.save()
            except Exception as e:
                currency = Currency.objects.get(short_name='USDT')
                course_hist = CourseHistory(currency=currency)
                course_hist.old_value = 0
                course_hist.new_value = float(course_main)
                course_hist.save()
                direction = 'up'
                variation = 0
                errors_list.append(str(e))

            course_5 = course_main * (Decimal(1 + (course_percent / 100)))
            course_tadg = course_5 + 3
            course_delivery = course_main * (Decimal(1 + (3 / 100)))
            course_5 = course_5.quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)
            course_delivery = course_delivery.quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)
            if user.id != 1:
                return Response({'rates': [
                        {'name': 'Наличные', 'value': course_5, 'direction': direction, 'variation': variation},
                        {'name': 'Рапира', 'value': '-', 'direction': direction, 'variation': variation},
                        {'name': 'Таджикистан', 'value': course_tadg, 'direction': direction, 'variation': variation},
                        {'name': 'Логистика', 'value': course_delivery, 'direction': direction, 'variation': variation},
                ]}, status=200)

            else:
                return Response({'rates': [
                    {'name': 'Наличные', 'value': course_5, 'direction': direction, 'variation': variation},
                    {'name': 'Рапира', 'value': course_main, 'direction': direction, 'variation': variation},
                    {'name': 'Таджикистан', 'value': course_tadg, 'direction': direction, 'variation': variation},
                    {'name': 'Логистика', 'value': course_delivery, 'direction': direction, 'variation': variation},
                ], 'errors': str(errors_list)}, status=200)
        except Exception as e:
            return Response({'rates': [
                    {'name': 'Ошибка получения', 'value': str(e), 'direction': 'up', 'variation': '0'}]})#Response({'error': "Ошибка получения данных с сервиса: {0}".format(str(e))}, status=200)


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

class GetWarBalance(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from decimal import Decimal, ROUND_HALF_UP
        bill_name = request.GET.get('bill_name', 'USDT КИТАЙ')
        try:
            bill = Bill.objects.get(short_name=bill_name)
        except Bill.DoesNotExist:
            return Response({'detail': 'Нет счета'}, status=400)
        qs = IncomeExpense.objects.filter(
            income_account__short_name='USDT КИТАЙ',
            income_account__isnull=False
        )

        result = qs.aggregate(
            total_amount=Sum('income_amount'),
            weighted_sum=Sum(
                ExpressionWrapper(
                    F('income_amount') * F('rate_conversion'),
                    output_field=DecimalField(max_digits=28, decimal_places=10)
                )
            )
        )
        weighted_rate = (result['weighted_sum'] / result['total_amount']).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP) if result['total_amount'] else 0
        if weighted_rate != 0 and bill.remainder:
            remainder = (weighted_rate * bill.remainder).quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)
        else:
            remainder = 0
        return Response({'rate': weighted_rate, 'remainder': remainder}, status=200)

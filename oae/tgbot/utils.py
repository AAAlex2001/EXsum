import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.db.models import (
    Q,
    F,
    Sum,
    Case,
    When,
    Value,
    DecimalField,
    ExpressionWrapper,
)
from django.db.models.functions import TruncDay, TruncMonth
from catalog.models import *
from dashboard.utils import get_ip_income
from operation.models import *
from django.utils import timezone





def get_revenue_months_list():
    # Берем все уникальные месяцы, в которых есть закрытые сделки
    months = (
        IncomeExpense.objects
        .filter(deal__closed=True)
        .annotate(month=TruncMonth('date_create'))
        .values_list('month', flat=True)
        .distinct()
        .order_by('month')
    )

    # Форматируем в 'мм.гггг'
    return [d.date().strftime('%m.%Y') for d in months]



def get_revenue_days_list():
    today = datetime.datetime.today()
    prev_month_date = today - relativedelta(months=1)

    year, month = prev_month_date.year, prev_month_date.month

    days = (
        IncomeExpense.objects
        .filter(
            date_create__year=year,
            date_create__month=month,
            deal__closed=True,
        )
        .annotate(day=TruncDay('date_create'))
        .values_list('day', flat=True)
        .distinct()
        .order_by('day')
    )

    return [d.date().strftime('%d.%m.%Y') for d in days]

def get_dds_detail(month_str: str):
    data = {}
    all_data = {}
    all_data['month_str'] = month_str
    all_data['incomes'] = []
    all_data['expenses'] = []
    usd_currencies = ['USD', 'USDT']
    month, year = map(int, month_str.split('.'))
    start_dt = timezone.make_aware(
        datetime.datetime(year, month, 1, 0, 0, 0)
    )
    end_dt = (start_dt + relativedelta(months=1)) - datetime.timedelta(microseconds=1)
    cashflows = CashFlow.objects.filter(status=True, type_cf='expense')
    total_expense = 0
    for cashflow in cashflows:
        expense = 0
        deals = Deal.objects.filter(
            cashflow=cashflow,
            date_create__range=(start_dt, end_dt),
        )
        for deal in deals:
            in_exes = IncomeExpense.objects.filter(deal=deal)
            for in_ex in in_exes:
                if in_ex.expense_account:
                    if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                        expense += in_ex.expense_amount * in_ex.expense_rate
                    else:
                        expense += in_ex.expense_amount
        total_expense += expense

        #if expense != 0:
        data[cashflow.name + ' - ']= Decimal(expense).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        all_data['expenses'].append({cashflow.name: Decimal(expense).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)})
    data['📉 Расходы компании: '] = Decimal(total_expense).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    all_data['all_expense'] = Decimal(total_expense).quantize(Decimal("0.001"))
    cashflows = CashFlow.objects.filter(status=True, type_cf='income')
    total_income = 0
    for cashflow in cashflows:
        income = 0
        deals = Deal.objects.filter(
            cashflow=cashflow,
            date_create__range=(start_dt, end_dt),
        )
        for deal in deals:
            in_exes = IncomeExpense.objects.filter(deal=deal)
            for in_ex in in_exes:
                if in_ex.income_account:
                    if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                        income += in_ex.income_amount * in_ex.income_rate
                    else:
                        income += in_ex.income_amount
        total_income += income

        #if income != 0:
        data[cashflow.name + ' - ']= Decimal(income).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        all_data['incomes'].append(
            {cashflow.name: Decimal(income).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)})
    data['📈 Доходы компании: '] = Decimal(total_income).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    income_value = F('income_amount')
    expense_value = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )
    net_value = ExpressionWrapper(income_value - expense_value, output_field=DecimalField())

    income_value_1 = ExpressionWrapper(
        F('expense_amount') * F('deal__rate'),
        output_field=DecimalField()
    )
    expense_value_1 = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )
    net_value_1 = ExpressionWrapper(income_value_1 - expense_value_1, output_field=DecimalField())

    cond1 = Q(
        income_account__currency__short_name='RUB',
        expense_account__currency__short_name__in=usd_currencies
    )
    cond2 = Q(
        income_account__isnull=True,
        expense_account__currency__short_name__in=usd_currencies
    )

    base_filter = Q(
        date_create__range=(start_dt, end_dt),
        deal__closed=True,
        deal__category__id__in=[2, 4],
    )

    net = (
            IncomeExpense.objects
            .filter(base_filter & (cond1 | cond2))
            .exclude(deal__contractor__id=1)
            .aggregate(
                total=Sum(
                    Case(
                        When(cond1, then=net_value),
                        When(cond2, then=net_value_1),
                        default=Value(0),
                        output_field=DecimalField()
                    )
                )
            )['total'] or Decimal("0")
    )
    monthly_ip_income = get_ip_income(
        period='months',
        start_date=start_dt,
        end_date=end_dt
    )
    net_profit = monthly_ip_income.get(month_str, Decimal("0"))

    all_income = net + net_profit
    data['Доход общий: '] = all_income.quantize(Decimal("0.001"))
    all_data['total_profit'] = all_income.quantize(Decimal("0.001"))
    all_data['all_income'] = Decimal(total_income + all_income).quantize(Decimal("0.001"))
    remainder = (all_income + total_income - total_expense).quantize(Decimal("0.001"))
    data['Остаток: '] = remainder.quantize(Decimal("0.001"))
    all_data['remainder'] = remainder.quantize(Decimal("0.001"))
    return data, all_data


def get_revenue_month_detail(month_str: str):
    """
    Возвращает данные по конкретному месяцу точно как в вебе
    """


    month, year = map(int, month_str.split('.'))
    start_dt = timezone.make_aware(
        datetime.datetime(year, month, 1, 0, 0, 0)
    )
    end_dt = (start_dt + relativedelta(months=1)) - datetime.timedelta(microseconds=1)

    contractor = Contractor.objects.get(id=1)
    usd_currencies = ['USD', 'USDT']

    # --------------------
    # Общий доход
    # --------------------
    income_value = F('income_amount')
    expense_value = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )
    net_value = ExpressionWrapper(income_value - expense_value, output_field=DecimalField())

    income_value_1 = ExpressionWrapper(
        F('expense_amount') * F('deal__rate'),
        output_field=DecimalField()
    )
    expense_value_1 = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )
    net_value_1 = ExpressionWrapper(income_value_1 - expense_value_1, output_field=DecimalField())

    cond1 = Q(
        income_account__currency__short_name='RUB',
        expense_account__currency__short_name__in=usd_currencies
    )
    cond2 = Q(
        income_account__isnull=True,
        expense_account__currency__short_name__in=usd_currencies
    )

    base_filter = Q(
        date_create__range=(start_dt, end_dt),
        deal__closed=True,
        deal__category__id__in=[2, 4],
    )

    net = (
        IncomeExpense.objects
        .filter(base_filter & (cond1 | cond2))
        .exclude(deal__contractor__id=1)
        .aggregate(
            total=Sum(
                Case(
                    When(cond1, then=net_value),
                    When(cond2, then=net_value_1),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        )['total'] or Decimal("0")
    )

    # --------------------
    # Комиссия USD
    # --------------------
    usd_commission = (
        IncomeExpense.objects
        .filter(
            date_create__range=(start_dt, end_dt),
            deal__closed=True,
            income_account__id__in=[8],
            expense_account__id__in=[16, 20],
        )
        .aggregate(total=Sum('commission'))
    )['total'] or Decimal("0")

    # --------------------
    # Моя метрика USD
    # --------------------
    net_value_usd = ExpressionWrapper(
        F('income_amount') - F('expense_amount') - F('commission'),
        output_field=DecimalField()
    )

    usd_metric = (
        IncomeExpense.objects
        .filter(
            date_create__range=(start_dt, end_dt),
            deal__closed=True,
            income_account__id__in=[16, 20],
            expense_account__id__in=[8],
        )
        .aggregate(total=Sum(net_value_usd))['total']
        or Decimal("0")
    )

    # --------------------
    # Моя метрика USDT
    # --------------------
    net_value_usdt = ExpressionWrapper(
        F('income_amount') - F('expense_amount'),
        output_field=DecimalField()
    )

    usdt = (
        IncomeExpense.objects
        .filter(
            date_create__range=(start_dt, end_dt),
            deal__closed=True,
            income_account__id__in=[9],
            expense_account__id__in=[8],
        )
        .aggregate(total=Sum(net_value_usdt))['total']
        or Decimal("0")
    )

    # --------------------
    # Никита
    # --------------------
    nikita = (
        Deal.objects
        .filter(
            by_nikita=True,
            closed=True,
            date_create__range=(start_dt, end_dt)
        )
        .aggregate(total=Sum('national_currency') * Decimal('0.01'))['total']
        or Decimal("0")
    )

    # --------------------
    # Доход ИП — ТОЛЬКО через get_ip_income
    # --------------------
    monthly_ip_income = get_ip_income(
        period='months',
        start_date=start_dt,
        end_date=end_dt
    )
    net_profit = monthly_ip_income.get(month_str, Decimal("0"))

    total_income = net + net_profit
    no_contractor = (
            IncomeExpense.objects
            .filter(
                base_filter,
                deal__contractor__isnull=True
            )
            .filter(cond1 | cond2)
            .aggregate(
                total=Sum(
                    Case(
                        When(cond1, then=net_value),
                        When(cond2, then=net_value_1),
                        default=Value(0),
                        output_field=DecimalField()
                    )
                )
            )['total'] or Decimal("0")
    )
    return {
        "Дата": month_str,
        "Доход общий": total_income.quantize(Decimal("0.001")),
        "Моя метрика USD": usd_metric.quantize(Decimal("0.001")),
        "Комиссия": usd_commission.quantize(Decimal("0.001")),
        "Моя метрика USDT": usdt.quantize(Decimal("0.001")),
        "Никита": nikita.quantize(Decimal("0.001")),
        "Доход ИП": net_profit.quantize(Decimal("0.001")),
        "Без контрагента": no_contractor.quantize(Decimal("0.001"))
    }


def get_revenue_day_detail(date_str: str):
    from dashboard.utils import get_ip_income
    """
    Возвращает данные по конкретному дню точно как в вебе.
    Совпадение с вебом по 'Моя метрика USD' и 'Комиссия'.
    """
    date = datetime.datetime.strptime(date_str, "%d.%m.%Y")
    year, month, day = date.year, date.month, date.day
    start_dt = timezone.make_aware(
        datetime.datetime(year, month, day, 0, 0, 0)
    )
    end_dt = timezone.make_aware(
        datetime.datetime(year, month, day, 23, 59, 59, 999999)
    )
    contractor = Contractor.objects.get(id=1)
    usd_currencies = ['USD', 'USDT']

    # --------------------
    # Общий доход
    # --------------------
    income_value = F('income_amount')
    expense_value = ExpressionWrapper(F('expense_amount') * F('expense_rate'), output_field=DecimalField())
    net_value = ExpressionWrapper(income_value - expense_value, output_field=DecimalField())

    income_value_1 = ExpressionWrapper(F('expense_amount') * F('deal__rate'), output_field=DecimalField())
    expense_value_1 = ExpressionWrapper(F('expense_amount') * F('expense_rate'), output_field=DecimalField())
    net_value_1 = ExpressionWrapper(income_value_1 - expense_value_1, output_field=DecimalField())

    cond1 = Q(income_account__currency__short_name='RUB', expense_account__currency__short_name__in=usd_currencies)
    cond2 = Q(income_account__isnull=True, expense_account__currency__short_name__in=usd_currencies)

    base_filter = Q(
        date_create__range=(start_dt, end_dt),
        deal__closed=True,
        deal__category__id__in=[2, 4],
    )

    net = (
        IncomeExpense.objects
        .filter(base_filter & (cond1 | cond2))
        .exclude(deal__contractor__id=1)
        .aggregate(
            total=Sum(
                Case(
                    When(cond1, then=net_value),
                    When(cond2, then=net_value_1),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        )['total'] or Decimal("0")
    )

    # Без контрагента (как в месячной логике)
    # --------------------
    no_contractor = (
            IncomeExpense.objects
            .filter(
                base_filter,
                deal__contractor__isnull=True
            )
            .filter(cond1 | cond2)
            .aggregate(
                total=Sum(
                    Case(
                        When(cond1, then=net_value),
                        When(cond2, then=net_value_1),
                        default=Value(0),
                        output_field=DecimalField()
                    )
                )
            )['total'] or Decimal("0")
    )

    # --------------------
    # Комиссия USD (как в вебе)
    # --------------------
    usd_commission = (
        IncomeExpense.objects
        .filter(
            date_create__range=(start_dt, end_dt),
            deal__closed=True,
            income_account__id__in=[8],
            expense_account__id__in=[16, 20],
        )
        .aggregate(total_commission=Sum('commission'))
    )['total_commission'] or Decimal('0')

    # --------------------
    # Моя метрика USD (не вычитаем комиссию дважды)
    # --------------------
    net_value_usd = ExpressionWrapper(F('income_amount') - F('expense_amount') - F('commission'), output_field=DecimalField())
    usd_row = (
        IncomeExpense.objects
        .filter(
            date_create__range=(start_dt, end_dt),
            deal__closed=True,
            income_account__id__in=[16, 20],  # как веб
            expense_account__id__in=[8],
        )
        .aggregate(total_net=Sum(net_value_usd))
    )
    usd_metric = usd_row['total_net'] or Decimal("0")

    # --------------------
    # Моя метрика USDT
    # --------------------
    net_value_usdt = ExpressionWrapper(F('income_amount') - F('expense_amount'), output_field=DecimalField())
    usdt = (
        IncomeExpense.objects
        .filter(
            date_create__range=(start_dt, end_dt),
            deal__closed=True,
            income_account__id__in=[9],
            expense_account__id__in=[8],
        )
        .aggregate(total=Sum(net_value_usdt))['total'] or Decimal("0")
    )

    # --------------------
    # Никита
    # --------------------
    nikita = (
        Deal.objects
        .filter(by_nikita=True, closed=True,
                date_create__range=(start_dt, end_dt),)
        .aggregate(total=Sum('national_currency') * Decimal('0.01'))['total'] or Decimal("0")
    )

    # --------------------
    # Доход ИП
    # --------------------
    daily_ip_income = get_ip_income(
        period='days',
        start_date=start_dt,
        end_date=end_dt
    )
    net_profit = daily_ip_income.get(date.strftime('%d.%m.%Y'), Decimal("0"))
    total_income = net + net_profit
    # --------------------
    # Возвращаем словарь
    # --------------------
    return {
        "Дата": date.strftime('%d.%m.%Y'),
        "Доход общий": total_income.quantize(Decimal("0.001")),
        "Без контрагента": no_contractor.quantize(Decimal("0.001")),
        "Моя метрика USD": usd_metric.quantize(Decimal("0.001")),
        "Комиссия": usd_commission.quantize(Decimal("0.001")),
        "Моя метрика USDT": usdt.quantize(Decimal("0.001")),
        "Никита": nikita.quantize(Decimal("0.001")),
        "Доход ИП": net_profit.quantize(Decimal("0.001")),
    }










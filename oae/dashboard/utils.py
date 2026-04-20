from datetime import timedelta
from django.utils import timezone
from operation.models import IncomeExpense, Deal, DealRepayment,ContractorDebtOperation
from django.utils.timezone import now
import calendar
from collections import defaultdict
from django.db.models import Count, Sum, F, Sum, Case, When, DecimalField, ExpressionWrapper, Q, Value , Subquery, OuterRef, Min, Exists
from django.db.models.functions import ExtractWeekDay, TruncDay, TruncMonth, ExtractMonth, Coalesce
import datetime
from decimal import Decimal, ROUND_HALF_UP
from catalog.models import Contractor, CashFlow
import calendar
import locale
from collections import defaultdict



def check_debt_vs_repayments():
    contractor = Contractor.objects.get(id=1)

    # ===== Подсчёт полного долга по всем сделкам =====
    total_debt = contractor.duty  # начальный долг
    deals = Deal.objects.filter(contractor=contractor, closed=True).order_by('date_create')

    for deal in deals:
        try:
            in_ex = IncomeExpense.objects.get(deal=deal)
        except IncomeExpense.DoesNotExist:
            # Если нет IncomeExpense, берём duty_deal
            if getattr(deal, 'duty_deal', None):
                total_debt += deal.duty_deal
            continue

        # Расходные сделки
        if in_ex.expense_account and not in_ex.income_account:
            if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                total_debt += in_ex.expense_amount * deal.rate
            else:
                total_debt += in_ex.expense_amount
        # Приходные сделки (для долга контрагента считаем как "не уменьшает total_debt")
        # Обычно не добавляем, если только для проверки распределения

        # Если есть duty_deal без deal_data
        if getattr(deal, 'duty_deal', None) and not in_ex.expense_account:
            total_debt += deal.duty_deal

    # ===== Погашено через DealRepayment =====
    total_repaid = DealRepayment.objects.filter(
        calc__contractor=contractor
    ).aggregate(s=Sum('amount'))['s'] or Decimal(0)

    remaining_debt = total_debt - total_repaid

    print(f"Общий долг (по всем сделкам): {total_debt}")
    print(f"Погашено через DealRepayment: {total_repaid}")
    print(f"Остаток долга: {remaining_debt}")



def check_repayments():
    contractor = Contractor.objects.get(id=1)

    # Сумма по DealRepayment
    total_repaid = DealRepayment.objects.filter(
        calc__contractor=contractor
    ).aggregate(s=Sum('amount'))['s'] or Decimal(0)

    print(f"Фактически погашено через DealRepayment: {total_repaid}")


def get_all_ip_check():
    from decimal import Decimal


    contractor = Contractor.objects.get(id=1)

    # Общий долг — начальный долг + все расходные сделки
    total_debt = contractor.duty
    expense_deals = list(
        Deal.objects.filter(contractor=contractor, closed=True).filter(
            deal_data__income_account__isnull=True
        ).order_by('date_create')
    )
    duty_only_deals = list(
        Deal.objects.filter(contractor=contractor, closed=True).filter(
            deal_data__isnull=True,
            duty_deal__isnull=False
        ).order_by('date_create')
    )
    all_expense_deals = sorted(expense_deals + duty_only_deals, key=lambda d: d.date_create)

    for deal in all_expense_deals:
        if deal.deal_data.exists():
            exp = deal.deal_data.first()
            if exp.expense_account.currency.short_name in ['USD', 'USDT']:
                total_debt += exp.expense_amount * deal.rate
            else:
                total_debt += exp.expense_amount
        elif getattr(deal, 'duty_deal', None):
            total_debt += deal.duty_deal

    # Оплачено через DealRepayment
    total_repaid = DealRepayment.objects.filter(
        calc__contractor=contractor
    ).aggregate(s=Sum('amount'))['s'] or Decimal(0)

    # Остаток долга
    remaining_debt = total_debt - total_repaid

    print(f"Общий долг: {total_debt}")
    print(f"Погашено: {total_repaid}")
    print(f"Остаток: {remaining_debt}")

def get_all_ip():
    contractor = Contractor.objects.get(id=1)
    total_income = 0
    contractor_duty = contractor.duty
    total_expense = 0
    total_expense += contractor_duty
    deals = Deal.objects.filter(contractor=contractor, closed=True).order_by('date_create')
    for deal in deals:
        try:
            in_ex = IncomeExpense.objects.get(deal=deal)
        except:
            total_expense += deal.duty_deal
            continue
        if in_ex.income_account and not in_ex.expense_account:
            if in_ex.income_account.currency.short_name in ['USDT', 'USD']:
                total_income += in_ex.income_amount * in_ex.income_rate
            else:
                total_income += in_ex.income_amount
        if in_ex.expense_account and not in_ex.income_account:
            if in_ex.expense_account.currency.short_name in ['USDT', 'USD']:
                total_expense += in_ex.expense_amount * deal.rate
            else:
                total_expense += in_ex.expense_amount
    print(total_income, total_expense)
    print(total_expense - total_income)

def get_revenue_months_by_contractor_values_only():
    from dateutil.relativedelta import relativedelta
    usd_currencies = ['USD', 'USDT']
    start_date = IncomeExpense.objects.filter(
        deal__closed=True
    ).aggregate(min_date=Min('date_create'))['min_date']

    if start_date is None:
        start_date = timezone.now()

    end_date = timezone.now()



    income_value = F('income_amount')
    expense_value = ExpressionWrapper(
    F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )

    net_value = ExpressionWrapper(
        income_value - expense_value,
        output_field=DecimalField()
    )

    income_value_1 = ExpressionWrapper(
        F('expense_amount') * F('deal__rate'),
        output_field=DecimalField()
    )
    expense_value_1 = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )

    net_value_1 = ExpressionWrapper(
        income_value_1 - expense_value_1,
        output_field=DecimalField()
    )

    cond1 = Q(
        income_account__currency__short_name='RUB',
        expense_account__currency__short_name__in=usd_currencies
    )
    cond2 = Q(
        income_account__isnull=True,
        expense_account__currency__short_name__in=usd_currencies
    )


    base_filter = Q(
        date_create__range=(start_date, end_date),
        deal__closed=True,
        deal__category__id__in=[2, 4],
    ) & ~Q(deal__contractor__id=1)

    total_qs = (
        IncomeExpense.objects
        .filter(base_filter & (cond1 | cond2))
        .annotate(month=TruncMonth('date_create'))
        .values('month')
        .annotate(total_net=Sum(
            Case(
                When(cond1, then=net_value),
                When(cond2, then=net_value_1),
                default=Value(0),
                output_field=DecimalField()
            )
        ))
        .order_by('month')
    )
    """contractor_qs = (
        IncomeExpense.objects
        .filter(base_filter & (cond1 | cond2))
        .annotate(month=TruncMonth('date_create'))
        .values('month', 'deal__contractor__name','deal__id')
        .annotate(c_net=Sum(
            Case(
                When(cond1, then=net_value),
                When(cond2, then=net_value_1),
                default=Value(0),
                output_field=DecimalField()
            )
        ))
        .order_by('month', 'deal__contractor__name')
    )"""
    debt_writeoff_exists = ContractorDebtOperation.objects.filter(
        deal_id=OuterRef('deal_id'),
        operation_type='write_off',
        amount=OuterRef('expense_amount'),
        currency_id=OuterRef('expense_account__currency_id')
    )

    # --- Query ---
    contractor_qs = (
        IncomeExpense.objects
        .filter(base_filter)
        .annotate(
            has_writeoff=Exists(debt_writeoff_exists),
            month=TruncMonth('date_create')
        )
        .filter(cond1 | cond2)
        .values('month', 'deal__contractor__name', 'deal__id')
        .annotate(
            c_net=Sum(
                Case(
                    # обычный случай
                    When(cond1, then=net_value),

                    # cond2 ТОЛЬКО если нет write_off
                    When(cond2 & Q(has_writeoff=False), then=net_value_1),

                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        )
        .order_by('month', 'deal__contractor__name')
    )
    deals_with_profit = (
        Deal.objects
        .filter(closed=True)
        .annotate(month=TruncMonth('date_create'))
        .annotate(
            ie_usdt_expense_count=Count('deal_data', filter=Q(
                deal_data__income_account__isnull=True,
                deal_data__expense_account__currency__short_name='USDT'
            ), distinct=True),

            debt_writeoff_rub_count=Count('debt_operations', filter=Q(
                debt_operations__operation_type='write_off',
                debt_operations__currency__short_name='RUB'
            ), distinct=True),

            ie_expense_usd=Coalesce(Sum(
                ExpressionWrapper(F('deal_data__expense_amount') * F('deal_data__expense_rate'),
                                  output_field=DecimalField()),
                filter=Q(deal_data__income_account__isnull=True,
                         deal_data__expense_account__currency__short_name='USDT')
            ), Value(0, output_field=DecimalField())),

            debt_writeoff_rub_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
                debt_operations__operation_type='write_off',
                debt_operations__currency__short_name='RUB'
            )), Value(0, output_field=DecimalField())),

            debt_writeoff_non_usd_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
                debt_operations__operation_type='write_off'
            ) & ~Q(debt_operations__currency__short_name__in=['USD', 'USDT'])),
                                               Value(0, output_field=DecimalField())),

            usdt_writeon_sum=Coalesce(Sum(
                ExpressionWrapper(F('debt_operations__amount') * F('rate_contractors'),
                                  output_field=DecimalField()),
                filter=Q(debt_operations__operation_type='write_on', debt_operations__currency__short_name='USDT')
            ), Value(0, output_field=DecimalField())),
        )
        .annotate(
            c_net=Case(
                When(ie_usdt_expense_count=1, debt_writeoff_rub_count=1,
                     then=F('debt_writeoff_rub_sum') - F('ie_expense_usd')),
                When(ie_usdt_expense_count=0, debt_writeoff_non_usd_sum__gt=0, usdt_writeon_sum__gt=0,
                     then=F('debt_writeoff_non_usd_sum') - F('usdt_writeon_sum')),
                default=Value(0, output_field=DecimalField()),
                output_field=DecimalField()
            )
        )
        .values('month', 'debt_operations__contractor__name', 'c_net')  # Получаем плоский список
    )
    combined_map = defaultdict(dict)

    # Добавляем данные из contractor_qs
    for rec in contractor_qs:
        print(rec)
        month = rec['month'].date().replace(day=1)
        name = rec['deal__contractor__name'] or 'Без контрагента'
        value = rec['c_net'].quantize(Decimal("0.001"), ROUND_HALF_UP)
        combined_map[month][name] = value

    # Добавляем данные из deals_with_profit, суммируем если уже есть
    for rec in deals_with_profit:
        #print(rec)
        month = rec['month'].date().replace(day=1)  # Приводим день к первому дню месяца
        name = rec.get('debt_operations__contractor__name') or 'Без контрагента'
        value = Decimal(rec['c_net']).quantize(Decimal("0.001"), ROUND_HALF_UP)
        if name in combined_map[month]:
            combined_map[month][name] += value
        else:
            combined_map[month][name] = value

    contractors = sorted({
        name or 'Без контрагента'
        for month_data in combined_map.values()
        for name in month_data.keys()
    })

    return combined_map, contractors







def get_dds_table():
    cashflows = CashFlow.objects.filter(status=True)
    current_year = now().year
    years = [current_year - 1, current_year]

    # собираем месяцы за прошлый и текущий год
    month_list = []
    extra_profit_months = {}
    ie_subquery = (
        IncomeExpense.objects
        .filter(
            deal_id=OuterRef('pk'),
            income_account__isnull=True,
            expense_account__currency__short_name='USDT'
        )
        .annotate(
            has_writeoff=Exists(
                ContractorDebtOperation.objects.filter(
                    deal_id=OuterRef('deal_id'),
                    operation_type='write_off',
                    amount=OuterRef('expense_amount'),
                    currency_id=OuterRef('expense_account__currency_id')
                )
            )
        )
        .filter(has_writeoff=False)
        .annotate(
            val=ExpressionWrapper(
                F('expense_amount') * F('expense_rate'),
                output_field=DecimalField()
            )
        )
        .values('deal_id')
        .annotate(total=Sum('val'))
        .values('total')[:1]
    )
    deals_with_extra = Deal.objects.filter(closed=True).annotate(
        ie_usdt_expense_count=Count('deal_data', filter=Q(
            deal_data__income_account__isnull=True,
            deal_data__expense_account__currency__short_name='USDT'
        ), distinct=True),
        debt_writeoff_rub_count=Count('debt_operations', filter=Q(
            debt_operations__operation_type='write_off',
            debt_operations__currency__short_name='RUB'
        ), distinct=True),
        ie_expense_usd=Coalesce(
            Subquery(ie_subquery),
            Value(0, output_field=DecimalField())
        ),
        debt_writeoff_rub_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
            debt_operations__operation_type='write_off',
            debt_operations__currency__short_name='RUB'
        )), Value(0, output_field=DecimalField())),
        debt_writeoff_non_usd_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
            debt_operations__operation_type='write_off'
        ) & ~Q(debt_operations__currency__short_name__in=['USD', 'USDT'])),
                                           Value(0, output_field=DecimalField())),
        usdt_writeon_sum=Coalesce(Sum(
            ExpressionWrapper(F('debt_operations__amount') * F('rate_contractors'),
                              output_field=DecimalField()),
            filter=Q(debt_operations__operation_type='write_on', debt_operations__currency__short_name='USDT')
        ), Value(0, output_field=DecimalField())),
    ).annotate(
        deal_profit=Case(
            When(ie_usdt_expense_count=1, debt_writeoff_rub_count=1,
                 then=F('debt_writeoff_rub_sum') - F('ie_expense_usd')),
            When(ie_usdt_expense_count=0, debt_writeoff_non_usd_sum__gt=0, usdt_writeon_sum__gt=0,
                 then=F('debt_writeoff_non_usd_sum') - F('usdt_writeon_sum')),
            default=Value(0, output_field=DecimalField()),
            output_field=DecimalField()
        )
    ).values('date_create__year', 'date_create__month', 'deal_profit')
    """deals_with_extra = Deal.objects.filter(closed=True).annotate(
        ie_usdt_expense_count=Count('deal_data', filter=Q(
            deal_data__income_account__isnull=True,
            deal_data__expense_account__currency__short_name='USDT'
        ), distinct=True),
        debt_writeoff_rub_count=Count('debt_operations', filter=Q(
            debt_operations__operation_type='write_off',
            debt_operations__currency__short_name='RUB'
        ), distinct=True),
        ie_expense_usd=Coalesce(Sum(
            ExpressionWrapper(F('deal_data__expense_amount') * F('deal_data__expense_rate'),
                              output_field=DecimalField()),
            filter=Q(deal_data__income_account__isnull=True,
                     deal_data__expense_account__currency__short_name='USDT')
        ), Value(0, output_field=DecimalField())),
        debt_writeoff_rub_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
            debt_operations__operation_type='write_off',
            debt_operations__currency__short_name='RUB'
        )), Value(0, output_field=DecimalField())),
        debt_writeoff_non_usd_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
            debt_operations__operation_type='write_off'
        ) & ~Q(debt_operations__currency__short_name__in=['USD', 'USDT'])),
                                           Value(0, output_field=DecimalField())),
        usdt_writeon_sum=Coalesce(Sum(
            ExpressionWrapper(F('debt_operations__amount') * F('rate_contractors'),
                              output_field=DecimalField()),
            filter=Q(debt_operations__operation_type='write_on', debt_operations__currency__short_name='USDT')
        ), Value(0, output_field=DecimalField())),
    ).annotate(
        deal_profit=Case(
            When(ie_usdt_expense_count=1, debt_writeoff_rub_count=1,
                 then=F('debt_writeoff_rub_sum') - F('ie_expense_usd')),
            When(ie_usdt_expense_count=0, debt_writeoff_non_usd_sum__gt=0, usdt_writeon_sum__gt=0,
                 then=F('debt_writeoff_non_usd_sum') - F('usdt_writeon_sum')),
            default=Value(0, output_field=DecimalField()),
            output_field=DecimalField()
        )
    ).values('date_create__year', 'date_create__month', 'deal_profit')"""

    for d in deals_with_extra:
        key = (d['date_create__year'], d['date_create__month'])
        extra_profit_months[key] = extra_profit_months.get(key, Decimal("0")) + (d['deal_profit'] or Decimal("0"))
    for year in years:
        months = (
            Deal.objects
            .filter(date_create__year=year)
            .annotate(month=ExtractMonth('date_create'))
            .values_list('month', flat=True)
            .distinct()
            .order_by('month')
        )
        month_list.extend([(year, m) for m in months])

    # убираем дубликаты и сортируем
    month_list = sorted(
        list(dict.fromkeys(month_list)),
        key=lambda x: (x[0], x[1])
    )

    cashflows_data = []
    total_income = []
    total_expense = []
    total_remainder = ['Остаток']

    # -------- Приходы --------
    cashflows_data.append(['Приходы'])
    cashflows = CashFlow.objects.filter(status=True, type_cf='income')
    for cashflow in cashflows:
        cashflow_data = [cashflow.name]
        for year, month in month_list:
            income = 0
            deals = Deal.objects.filter(
                cashflow=cashflow,
                date_create__year=year,
                date_create__month=month
            )
            for deal in deals:
                in_exes = IncomeExpense.objects.filter(deal=deal)
                for in_ex in in_exes:
                    if in_ex.income_account:
                        if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                            income += in_ex.income_amount * in_ex.income_rate
                        else:
                            income += in_ex.income_amount

            cashflow_data.append(
                Decimal(income).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            )

        if any(value != 0 for value in cashflow_data[1:]):
            cashflows_data.append(cashflow_data)

    cashflows_data.append(get_revenue_for_dds())

    # -------- Расходы --------
    cashflows_data.append(['Расходы'])
    cashflows = CashFlow.objects.filter(status=True, type_cf='expense')
    for cashflow in cashflows:
        cashflow_data = [cashflow.name]
        for year, month in month_list:
            expense = 0
            deals = Deal.objects.filter(
                cashflow=cashflow,
                date_create__year=year,
                date_create__month=month
            )
            for deal in deals:
                in_exes = IncomeExpense.objects.filter(deal=deal)
                for in_ex in in_exes:
                    if in_ex.expense_account:
                        if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                            expense += in_ex.expense_amount * in_ex.expense_rate
                        else:
                            expense += in_ex.expense_amount

            cashflow_data.append(
                Decimal(expense).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            )

        if any(value != 0 for value in cashflow_data[1:]):
            cashflows_data.append(cashflow_data)

    # -------- Остаток --------
    for year, month in month_list:
        income = Decimal("0")
        expense = Decimal("0")
        deals = Deal.objects.filter(
            date_create__year=year,
            date_create__month=month,
            cashflow__isnull=False,
            cashflow__status=True,
            cashflow__type_cf='income'
        )
        print(month)
        for deal in deals:
            print(deal.id)
            print('income ', income)
            in_exes = IncomeExpense.objects.filter(deal=deal)
            for in_ex in in_exes:
                if in_ex.deal.cashflow:
                    if in_ex.income_account:
                        if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                            income += in_ex.income_amount * in_ex.income_rate
                        else:
                            income += in_ex.income_amount
        extra = extra_profit_months.get((year, month), Decimal("0"))
        #income += Decimal(extra)
        print('extra ', extra)
        total_income.append(income)
        print('total income:', income)
    for year, month in month_list:
        income = 0
        expense = 0
        deals = Deal.objects.filter(
            date_create__year=year,
            date_create__month=month,
            cashflow__isnull=False,
            cashflow__status=True,
            cashflow__type_cf='expense'
        )
        for deal in deals:
            in_exes = IncomeExpense.objects.filter(deal=deal)
            for in_ex in in_exes:
                if in_ex.deal.cashflow:
                    if in_ex.expense_account:
                        if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                            expense += in_ex.expense_amount * in_ex.expense_rate
                        else:
                            expense += in_ex.expense_amount
        total_expense.append(expense)
        print('total expense:', expense)

    all_income = get_revenue_for_dds()
    all_income_values = all_income[1:]

    # добавляем extra profit
    """for i, (year, month) in enumerate(month_list):
        extra = extra_profit_months.get((year, month), Decimal("0"))
        all_income_values[i] += extra.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)"""

    # рассчитываем остаток сразу правильно
    total_remainder = ['Остаток']
    """for i, (year, month) in enumerate(month_list, start=1):
        extra = extra_profit_months.get((year, month), Decimal("0"))
        all_income[i] += extra.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)"""
    total_remainder += [
        Decimal(a - b).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        for a, b in zip(total_income, total_expense)
    ]

    for i in range(1, len(all_income)):
        print(total_remainder[i])
        print(all_income[i])
        total_remainder[i] += all_income[i]






    cashflows_data.append(total_remainder)
    return cashflows_data








def get_dds_columns():
    months_list = ['ДДС']
    current_year = now().year
    years = [current_year - 1, current_year]

    month_labels = []

    for year in years:
        months = (
            Deal.objects
            .filter(date_create__year=year)
            .annotate(month=ExtractMonth('date_create'))
            .values_list('month', flat=True)
            .distinct()
            .order_by('month')
        )

        try:
            locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
            month_names = [f"{calendar.month_name[m].capitalize()} {year}" for m in months if m]
        except locale.Error:
            month_name_map = {
                1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
                5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
                9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
            }
            month_names = [f"{month_name_map.get(m, f'Месяц {m}')} {year}" for m in months if m]

        month_labels.extend(month_names)

    months_list += month_labels
    return months_list


"""def get_revenue_for_dds():
    usd_currencies = ['USD', 'USDT']
    today = datetime.date.today()
    years = [today.year - 1, today.year]
    start_year_date = datetime.datetime(today.year - 1, 1, 1)
    end_date = today
    today = timezone.localtime(timezone.now())
    end_date = today
    # Собираем все месяцы для двух лет
    month_list = []
    for year in years:
        months = (
            Deal.objects
            .filter(date_create__year=year)
            .annotate(m=ExtractMonth('date_create'))
            .values_list('m', flat=True)
            .distinct()
            .order_by('m')
        )
        month_list.extend([(year, m) for m in months])

    # Убираем дубликаты и сортируем
    month_list = sorted(list(dict.fromkeys(month_list)), key=lambda x: (x[0], x[1]))

    monthly_net = ['Доход общий']
    monthly_ip_income = get_ip_income(
        period='months',
        start_date=start_year_date,
        end_date=end_date
    )
    for year, month in month_list:
        cond1 = Q(
            income_account__currency__short_name='RUB',
            expense_account__currency__short_name__in=usd_currencies
        )

        cond2 = Q(
            income_account__isnull=True,
            expense_account__currency__short_name__in=usd_currencies
        )

        base_filter = Q(
            date_create__year=year,
            deal__closed=True,
            deal__category__id__in=[2, 4],
        )

        income_value = F('income_amount')
        expense_value = ExpressionWrapper(
            F('expense_amount') * F('expense_rate'),
            output_field=DecimalField()
        )
        net_value = ExpressionWrapper(income_value - expense_value, output_field=DecimalField())

        income_value_1 = ExpressionWrapper(F('expense_amount') * F('deal__rate'), output_field=DecimalField())
        expense_value_1 = ExpressionWrapper(F('expense_amount') * F('expense_rate'), output_field=DecimalField())
        net_value_1 = ExpressionWrapper(income_value_1 - expense_value_1, output_field=DecimalField())

        qs = (
            IncomeExpense.objects
            .filter(base_filter, date_create__month=month)
            .exclude(deal__contractor__id=1)
            .annotate(
                has_writeoff=Exists(
                    ContractorDebtOperation.objects.filter(
                        deal_id=OuterRef('deal_id'),
                        operation_type='write_off',
                        amount=OuterRef('expense_amount'),
                        currency_id=OuterRef('expense_account__currency_id')
                    )
                )
            )
            .filter(cond1 | cond2)
            .annotate(
                net=Case(
                    When(cond1, then=net_value),

                    # 👇 ВАЖНО: добавили исключение
                    When(cond2 & Q(has_writeoff=False), then=net_value_1),

                    default=Value(0),
                    output_field=DecimalField()
                )
            )
            .aggregate(total_net=Sum('net'))
        )

        value = qs['total_net'] or Decimal(0)
        date_str = f"{month:02d}.{year}"
        total = value + monthly_ip_income.get(date_str, Decimal("0.000"))
        monthly_net.append(
            total.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        )
        #monthly_net.append(value.quantize(Decimal("0.001") + monthly_ip_income.get(date_str, Decimal("0.000"))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))

    return monthly_net"""

def get_revenue_for_dds():
    usd_currencies = ['USD', 'USDT']

    today = timezone.localtime(timezone.now())
    start_year_date = datetime.datetime(today.year - 1, 1, 1)
    end_date = today

    years = [today.year - 1, today.year]

    month_list = []
    for year in years:
        months = (
            Deal.objects
            .filter(date_create__year=year)
            .annotate(m=ExtractMonth('date_create'))
            .values_list('m', flat=True)
            .distinct()
            .order_by('m')
        )
        month_list.extend([(year, m) for m in months])

    month_list = sorted(list(dict.fromkeys(month_list)), key=lambda x: (x[0], x[1]))

    monthly_net = ['Доход общий']

    monthly_ip_income = get_ip_income(
        period='months',
        start_date=start_year_date,
        end_date=end_date
    )

    cond1 = Q(
        income_account__currency__short_name='RUB',
        expense_account__currency__short_name__in=usd_currencies
    )

    cond2 = Q(
        income_account__isnull=True,
        expense_account__currency__short_name__in=usd_currencies
    )

    income_value = F('income_amount')

    expense_value = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )

    net_value = ExpressionWrapper(
        income_value - expense_value,
        output_field=DecimalField()
    )

    income_value_1 = ExpressionWrapper(
        F('expense_amount') * F('deal__rate'),
        output_field=DecimalField()
    )

    expense_value_1 = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )

    net_value_1 = ExpressionWrapper(
        income_value_1 - expense_value_1,
        output_field=DecimalField()
    )

    debt_writeoff_exists = ContractorDebtOperation.objects.filter(
        deal_id=OuterRef('deal_id'),
        operation_type='write_off',
        amount=OuterRef('expense_amount'),
        currency_id=OuterRef('expense_account__currency_id')
    )

    # -------- deals_with_profit --------

    deals_profit_qs = (
        Deal.objects
        .filter(closed=True)
        .annotate(month=TruncMonth('date_create'))
        .annotate(
            ie_usdt_expense_count=Count(
                'deal_data',
                filter=Q(
                    deal_data__income_account__isnull=True,
                    deal_data__expense_account__currency__short_name='USDT'
                ),
                distinct=True
            ),

            debt_writeoff_rub_count=Count(
                'debt_operations',
                filter=Q(
                    debt_operations__operation_type='write_off',
                    debt_operations__currency__short_name='RUB'
                ),
                distinct=True
            ),

            ie_expense_usd=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F('deal_data__expense_amount') * F('deal_data__expense_rate'),
                        output_field=DecimalField()
                    ),
                    filter=Q(
                        deal_data__income_account__isnull=True,
                        deal_data__expense_account__currency__short_name='USDT'
                    )
                ),
                Value(0),
                output_field=DecimalField()
            ),

            debt_writeoff_rub_sum=Coalesce(
                Sum(
                    'debt_operations__amount',
                    filter=Q(
                        debt_operations__operation_type='write_off',
                        debt_operations__currency__short_name='RUB'
                    )
                ),
                Value(0),
                output_field=DecimalField()
            ),

            debt_writeoff_non_usd_sum=Coalesce(
                Sum(
                    'debt_operations__amount',
                    filter=Q(debt_operations__operation_type='write_off')
                    & ~Q(debt_operations__currency__short_name__in=['USD', 'USDT'])
                ),
                Value(0),
                output_field=DecimalField()
            ),

            usdt_writeon_sum=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F('debt_operations__amount') * F('rate_contractors'),
                        output_field=DecimalField()
                    ),
                    filter=Q(
                        debt_operations__operation_type='write_on',
                        debt_operations__currency__short_name='USDT'
                    )
                ),
                Value(0),
                output_field=DecimalField()
            ),
        )
        .annotate(
            c_net=Case(
                When(
                    ie_usdt_expense_count=1,
                    debt_writeoff_rub_count=1,
                    then=F('debt_writeoff_rub_sum') - F('ie_expense_usd')
                ),
                When(
                    ie_usdt_expense_count=0,
                    debt_writeoff_non_usd_sum__gt=0,
                    usdt_writeon_sum__gt=0,
                    then=F('debt_writeoff_non_usd_sum') - F('usdt_writeon_sum')
                ),
                default=Value(0),
                output_field=DecimalField()
            )
        )
        .values('month', 'c_net')
    )

    deals_profit_map = defaultdict(Decimal)

    for rec in deals_profit_qs:
        key = rec['month'].strftime('%m.%Y')
        deals_profit_map[key] += rec['c_net'] or Decimal("0")

    # -------- основной цикл --------

    for year, month in month_list:

        base_filter = Q(
            date_create__year=year,
            date_create__month=month,
            deal__closed=True,
            deal__category__id__in=[2, 4],
        ) & ~Q(deal__contractor__id=1)

        qs = (
            IncomeExpense.objects
            .filter(base_filter)
            .annotate(
                has_writeoff=Exists(debt_writeoff_exists)
            )
            .filter(cond1 | cond2)
            .annotate(
                net=Case(
                    When(cond1, then=net_value),
                    When(cond2 & Q(has_writeoff=False), then=net_value_1),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
            .aggregate(total_net=Sum('net'))
        )

        value = qs['total_net'] or Decimal(0)

        date_str = f"{month:02d}.{year}"
        total = (
            value
            + monthly_ip_income.get(date_str, Decimal("0"))
            + deals_profit_map.get(date_str, Decimal("0"))
        )

        monthly_net.append(
            total.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        )

    return monthly_net






def get_revenue_chart(type_view='days'):
    from dateutil.relativedelta import relativedelta
    usd_currencies = ['USD', 'USDT']
    income_value = F('income_amount')
    expense_value = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )

    net_value = ExpressionWrapper(income_value - expense_value, output_field=DecimalField())
    income_value_1 = ExpressionWrapper(F('expense_amount') * F('deal__rate'), output_field=DecimalField())
    expense_value_1 = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )

    net_value_1 = ExpressionWrapper(income_value_1 - expense_value_1, output_field=DecimalField())
    today = datetime.datetime.today()
    prev_month_date = today - relativedelta(months=1)
    year = prev_month_date.year
   # year = today.year
    #month = today.month
    month = prev_month_date.year
    cond1 = Q(
        income_account__currency__short_name='RUB',
        expense_account__currency__short_name__in=usd_currencies
    )
    cond2 = Q(
        income_account__isnull=True,
        expense_account__currency__short_name__in=usd_currencies
    )
    if type_view == 'days':
        base_filter = Q(
            date_create__year=year,
            date_create__month=month,
            deal__closed=True,
            deal__category__id__in=[2, 4],
        )

        daily_qs = (
            IncomeExpense.objects
            .filter(base_filter & (cond1 | cond2))
            .annotate(day=TruncDay('date_create'))
            .values('day')
            .annotate(total_net=Sum(
                Case(
                    When(cond1, then=net_value),
                    When(cond2, then=net_value_1),
                    default=Value(0),
                    output_field=DecimalField()
                )
            ))
            .order_by('day')
        )
        daily_net = [
            (entry['day'].date().strftime('%d.%m.%Y'), entry['total_net'].quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
            for entry in daily_qs
        ]
        return daily_net
    elif type_view == 'months':
        base_filter = Q(
            date_create__year=year,
            deal__closed=True,
            deal__category__id__in=[2, 4],
        )
        monthly_qs = (
            IncomeExpense.objects
            .filter(base_filter & (cond1 | cond2))
            .annotate(month=TruncMonth('date_create'))
            .values('month')
            .annotate(total_net=Sum(
                Case(
                    When(cond1, then=net_value),
                    When(cond2, then=net_value_1),
                    default=Value(0),
                    output_field=DecimalField()
                )
            ))
            .order_by('month')
        )

        monthly_net = [
            (entry['month'].date().replace(day=1).strftime('%m.%Y'), entry['total_net'].quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
            for entry in monthly_qs
        ]
        return monthly_net


from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import (
    F, Sum, Case, When, Value,
    DecimalField, ExpressionWrapper
)
from django.db.models.functions import TruncDay, TruncMonth


def get_ip_income(period, start_date, end_date):
    usd = ['USD', 'USDT']
    result = defaultdict(Decimal)

    repayments = (
        DealRepayment.objects
        .filter(
            contractor_duty=False,
            duty__isnull=False,
            date_create__range=(start_date, end_date),
            duty__contractor_id=1,
            duty__closed=True,
        )
        .select_related('duty')  # только прямые FK
        .prefetch_related('duty__deal_data__expense_account__currency')  # обратные связи
    )

    fmt = '%d.%m.%Y' if period == 'days' else '%m.%Y'

    for r in repayments:
        duty = r.duty
        ie = duty.deal_data.first()  # prefetch_related делает это без лишнего запроса
        if not ie:
            continue

        if ie.expense_account.currency.short_name not in usd:
            continue

        if not duty.rate or not ie.expense_rate:
            continue

        profit = r.amount * (1 - ie.expense_rate / duty.rate)
        key = r.date_create.strftime(fmt)
        result[key] += profit

    return {
        k: v.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        for k, v in result.items()
    }


def get_revenue(type_view='days'):
    usd_currencies = ['USD', 'USDT']
    contractor = Contractor.objects.get(id=1)
    income_value = F('income_amount')
    expense_value = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )


    net_value = ExpressionWrapper(income_value - expense_value, output_field=DecimalField())
    income_value_1 = ExpressionWrapper(F('expense_amount') * F('deal__rate'), output_field=DecimalField())
    expense_value_1 = ExpressionWrapper(
        F('expense_amount') * F('expense_rate'),
        output_field=DecimalField()
    )

    net_value_1 = ExpressionWrapper(income_value_1 - expense_value_1, output_field=DecimalField())
    net_value_2 = ExpressionWrapper(F('income_amount') - F('expense_amount') - F('commission'), output_field=DecimalField())
    net_value_usdt = ExpressionWrapper(F('income_amount') - F('expense_amount'), output_field=DecimalField())

    #today = datetime.datetime.today()
    #year, month = today.year - 1, today.month - 1
    from dateutil.relativedelta import relativedelta
    today = datetime.datetime.today()



    cond1 = Q(
        income_account__currency__short_name='RUB',
        expense_account__currency__short_name__in=usd_currencies
    )
    cond2 = Q(
        income_account__isnull=True,
        expense_account__currency__short_name__in=usd_currencies
    )
    # NEW


    # -----------------------
    # ДНИ
    # -----------------------
    prev_month_date = today - relativedelta(months=1)
    if type_view == 'days':
        year, month = prev_month_date.year, prev_month_date.month
        start_date = (today.replace(day=1) - relativedelta(months=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_date = today
        daily_usd_commission_qs = (
            IncomeExpense.objects
            .filter(
                #date_create__year=year,
                #date_create__month=month,
                date_create__range=(start_date, end_date),
                deal__closed=True,
                income_account__id__in=[8],
                expense_account__id__in=[16, 20],
            )
            .annotate(day=TruncDay('date_create'))
            .values('day')
            .annotate(total_commission=Sum('commission'))
            .order_by('day')
        )

        daily_usd_commission = {
            entry['day'].date().strftime('%d.%m.%Y'):
                (entry['total_commission'] or Decimal('0'))
                .quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            for entry in daily_usd_commission_qs
        }
        base_filter = Q(
            #date_create__year=year,
            #date_create__month=month,
            date_create__range=(start_date, end_date),
            deal__closed=True,
            deal__category__id__in=[2, 4],
        )

        # Общий доход (убрал ип!!)

        daily_qs = (
            IncomeExpense.objects
            .filter(base_filter & (cond1 | cond2))
            .exclude(deal__contractor__id=1)
            # ИСКЛЮЧАЕМ сделки, у которых есть операции по долгам
            .exclude(deal__debt_operations__isnull=False)
            .annotate(day=TruncDay('date_create'))
            .values('day')
            .annotate(total_net=Sum(
                Case(
                    When(cond1, then=net_value),
                    When(cond2, then=net_value_1),
                    default=Value(0),
                    output_field=DecimalField()
                )
            ))
            .order_by('day')
        )
        # Nikita
        nikita_daily_qs = (
            Deal.objects
            .filter(
                by_nikita=True,
                closed=True,
                #date_create__year=year,
                #date_create__month=month,
                date_create__range=(start_date, end_date),
            )
            .annotate(day=TruncDay('date_create'))
            .values('day')
            .annotate(
                total_nc=Sum('national_currency'),
                nikita_percent=ExpressionWrapper(
                    Sum('national_currency') * Value(Decimal('0.01')),
                    output_field=DecimalField(max_digits=18, decimal_places=8)
                )
            )
            .order_by('day')
        )
        nikita_daily = {
            entry['day'].date().strftime('%d.%m.%Y'):
                (entry['nikita_percent'] or Decimal('0'))
                .quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            for entry in nikita_daily_qs
        }

        # 🔹 Отдельно USD
        base_filter_usd = Q(
            date_create__range=(start_date, end_date),
            deal__closed=True,
            income_account__id__in=[16, 20],
            expense_account__id__in=[8],
        )
        daily_qs_usd = (
            IncomeExpense.objects
            .filter(base_filter_usd)
            .annotate(day=TruncDay('date_create'))
            .annotate(net_value_2=net_value_2)
            .values('day')
            .annotate(total_net=Sum('net_value_2'), total_commission=Sum('commission'))
            .order_by('day')
        )

        # 🔹 Отдельно USDT
        base_filter_usdt = Q(
            date_create__range=(start_date, end_date),
            deal__closed=True,
            income_account__id__in=[9],
            expense_account__id__in=[8],
        )
        daily_qs_usdt = (
            IncomeExpense.objects
            .filter(base_filter_usdt)
            .annotate(day=TruncDay('date_create'))
            .annotate(net_value_2=net_value_usdt)
            .values('day')
            .annotate(total_net=Sum('net_value_2'))
            .order_by('day')
        )
        # NEW
        debug_date = '28.02.2026'
        print(f"\n=== Анализ daily_qs за {debug_date} ===")
        debug_qs = IncomeExpense.objects.filter(base_filter & (cond1 | cond2)).exclude(deal__contractor__id=1)

        for ie in debug_qs:
            if ie.date_create.strftime('%d.%m.%Y') == debug_date:
                # Определяем, какое условие сработало
                is_cond1 = ie.income_account and ie.income_account.currency.short_name == 'RUB'

                if is_cond1:
                    val = ie.income_amount - (ie.expense_amount * ie.expense_rate)
                    type_n = "COND1 (RUB->USD)"
                else:
                    val = (ie.expense_amount * ie.deal.rate) - (ie.expense_amount * ie.expense_rate)
                    type_n = "COND2 (NULL->USD)"

                print(f"Deal ID: {ie.deal.id} | Тип: {type_n}")
                print(f"  Расчет: {val}")
                print(f"  Курс сделки: {ie.deal.rate} | Курс расхода: {ie.expense_rate}")
                print(f"  Сумма прихода: {ie.income_amount} | Сумма расхода: {ie.expense_amount}")
        print("=== Конец анализа ===\n")

        # Форматируем результаты
        daily_net = [
            (entry['day'].date().strftime('%d.%m.%Y'),
             entry['total_net'].quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
            for entry in daily_qs
        ]
        daily_net_usd = {
            entry['day'].date().strftime('%d.%m.%Y'): (
                entry['total_net'].quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
                (entry['total_commission'] or Decimal("0"))
                .quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            )
            for entry in daily_qs_usd
        }
        daily_net_usdt = {
            entry['day'].date().strftime('%d.%m.%Y'):
            entry['total_net'].quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            for entry in daily_qs_usdt
        }
        # NEW!
        # 🔹 NEW! Чистая прибыль по дням (включая доходы на погашение долга)
        daily_ip_income = get_ip_income(
            period='days',
            start_date=start_date,
            end_date=end_date
        )

        # Объединяем с остальными данными

        NON_USD_USDT_CURRENCIES = ['RUB', ]
        deals_with_profit = (
            Deal.objects
            .filter(date_create__range=(start_date, end_date), closed=True)
            .annotate(day=TruncDay('date_create'))
            .annotate(
                # Считаем показатели внутри каждой конкретной сделки
                ie_usdt_expense_count=Count('deal_data', filter=Q(
                    deal_data__income_account__isnull=True,
                    deal_data__expense_account__currency__short_name='USDT'
                ), distinct=True),

                debt_writeoff_rub_count=Count('debt_operations', filter=Q(
                    debt_operations__operation_type='write_off',
                    debt_operations__currency__short_name='RUB'
                ), distinct=True),

                ie_expense_usd=Coalesce(Sum(
                    ExpressionWrapper(F('deal_data__expense_amount') * F('deal_data__expense_rate'),
                                      output_field=DecimalField()),
                    filter=Q(deal_data__income_account__isnull=True,
                             deal_data__expense_account__currency__short_name='USDT')
                ), Value(0, output_field=DecimalField())),

                debt_writeoff_rub_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
                    debt_operations__operation_type='write_off',
                    debt_operations__currency__short_name='RUB'
                )), Value(0, output_field=DecimalField())),

                debt_writeoff_non_usd_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
                    debt_operations__operation_type='write_off'
                ) & ~Q(debt_operations__currency__short_name__in=['USD', 'USDT'])),
                                                   Value(0, output_field=DecimalField())),

                usdt_writeon_sum=Coalesce(Sum(
                    ExpressionWrapper(F('debt_operations__amount') * F('rate_contractors'),
                                      output_field=DecimalField()),
                    filter=Q(debt_operations__operation_type='write_on', debt_operations__currency__short_name='USDT')
                ), Value(0, output_field=DecimalField())),
            )
            .annotate(
                deal_profit=Case(
                    When(ie_usdt_expense_count=1, debt_writeoff_rub_count=1,
                         then=F('debt_writeoff_rub_sum') - F('ie_expense_usd')),
                    When(ie_usdt_expense_count=0, debt_writeoff_non_usd_sum__gt=0, usdt_writeon_sum__gt=0,
                         then=F('debt_writeoff_non_usd_sum') - F('usdt_writeon_sum')),
                    default=Value(0, output_field=DecimalField()),
                    output_field=DecimalField()
                )
            )
            .values('day', 'deal_profit')  # Получаем плоский список
        )

        # 2. Группируем по дням на уровне Python, чтобы избежать FieldError
        extra_profit_dict = {}
        for row in deals_with_profit:
            date_str = row['day'].date().strftime('%d.%m.%Y')
            profit = row['deal_profit'] or Decimal("0")
            extra_profit_dict[date_str] = extra_profit_dict.get(date_str, Decimal("0")) + profit
        all_dates = set()
        all_dates |= {d for d, _ in daily_net}
        all_dates |= set(daily_ip_income.keys())
        all_dates |= set(daily_net_usd.keys())
        all_dates |= set(daily_net_usdt.keys())
        all_dates |= set(nikita_daily.keys())
        all_dates |= set(daily_usd_commission.keys())
        all_dates |= set(extra_profit_dict.keys())
        all_dates = sorted(
            all_dates,
            key=lambda d: datetime.datetime.strptime(d, '%d.%m.%Y')
        )
        daily_net_dict = dict(daily_net)


        daily_combined = [
            (
                date_str,
                (
                        daily_net_dict.get(date_str, Decimal("0.000"))
                        + daily_ip_income.get(date_str, Decimal("0.000"))
                        + extra_profit_dict.get(date_str, Decimal("0.000"))
                ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),

                daily_net_usd.get(date_str, (Decimal("0.000"), Decimal("0.000")))[0]
                .quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),

                daily_usd_commission.get(date_str, Decimal("0.000")),

                daily_net_usdt.get(date_str, Decimal("0.000")),

                nikita_daily.get(date_str, Decimal("0.000")),

                daily_ip_income.get(date_str, Decimal("0.000")),
            )
            for date_str in all_dates
        ]


        return daily_combined

    # -----------------------
    # МЕСЯЦЫ
    # -----------------------
    elif type_view == 'months':
        today = timezone.localtime(timezone.now())

        # Определяем минимальную дату из базы
        start_year_date = IncomeExpense.objects.filter(
            deal__closed=True
        ).aggregate(min_date=Min('date_create'))['min_date']

        if start_year_date is None:
            start_year_date = today
        else:
            if timezone.is_naive(start_year_date):
                start_year_date = timezone.make_aware(start_year_date)

        end_date = today

        # -----------------------
        # USD комиссия по месяцам
        # -----------------------
        monthly_usd_commission_qs = (
            IncomeExpense.objects
            .filter(
                date_create__range=(start_year_date, end_date),
                deal__closed=True,
                income_account__id__in=[8],
                expense_account__id__in=[16, 20],
            )
            .annotate(month=TruncMonth('date_create'))
            .values('month')
            .annotate(total_commission=Sum('commission'))
            .order_by('month')
        )
        monthly_usd_commission = {
            entry['month'].date().replace(day=1).strftime('%m.%Y'):
                (entry['total_commission'] or Decimal('0')).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            for entry in monthly_usd_commission_qs
        }

        # -----------------------
        # Общая прибыль по месяцам
        # -----------------------
        base_filter = Q(
            date_create__range=(start_year_date, end_date),
            deal__closed=True,
            deal__category__id__in=[2, 4],
        )
        monthly_qs = (
            IncomeExpense.objects
            .filter(base_filter & (cond1 | cond2))
            .exclude(deal__contractor__id=1)
            .exclude(deal__debt_operations__isnull=False)
            .annotate(month=TruncMonth('date_create'))
            .values('month')
            .annotate(total_net=Sum(
                Case(
                    When(cond1, then=net_value),
                    When(cond2, then=net_value_1),
                    default=Value(0),
                    output_field=DecimalField()
                )
            ))
            .order_by('month')
        )
        monthly_net = {
            entry['month'].date().replace(day=1).strftime('%m.%Y'):
                entry['total_net'].quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            for entry in monthly_qs
        }

        # -----------------------
        # Nikita
        # -----------------------
        nikita_monthly_qs = (
            Deal.objects
            .filter(by_nikita=True, closed=True)
            .annotate(month=TruncMonth('date_create'))
            .values('month')
            .annotate(
                nikita_percent=ExpressionWrapper(
                    Sum('national_currency') * Value(Decimal('0.01')),
                    output_field=DecimalField(max_digits=18, decimal_places=8)
                )
            )
            .order_by('month')
        )
        nikita_monthly = {
            entry['month'].date().replace(day=1).strftime('%m.%Y'):
                (entry['nikita_percent'] or Decimal('0')).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            for entry in nikita_monthly_qs
        }

        # -----------------------
        # USD чистая прибыль
        # -----------------------
        monthly_qs_usd = (
            IncomeExpense.objects
            .filter(
                date_create__range=(start_year_date, end_date),
                deal__closed=True,
                income_account__id__in=[16, 20],
                expense_account__id__in=[8],
            )
            .annotate(month=TruncMonth('date_create'))
            .annotate(net_value_2=net_value_2)
            .values('month')
            .annotate(total_net=Sum('net_value_2'), total_commission=Sum('commission'))
            .order_by('month')
        )
        monthly_net_usd = {
            entry['month'].date().replace(day=1).strftime('%m.%Y'): (
                entry['total_net'].quantize(Decimal("0.001"), rounding=ROUND_HALF_UP),
                (entry['total_commission'] or Decimal("0")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            )
            for entry in monthly_qs_usd
        }

        # -----------------------
        # USDT чистая прибыль
        # -----------------------
        monthly_qs_usdt = (
            IncomeExpense.objects
            .filter(
                date_create__range=(start_year_date, end_date),
                deal__closed=True,
                income_account__id__in=[9],
                expense_account__id__in=[8],
            )
            .annotate(month=TruncMonth('date_create'))
            .annotate(net_value_2=net_value_usdt)
            .values('month')
            .annotate(total_net=Sum('net_value_2'))
            .order_by('month')
        )
        monthly_net_usdt = {
            entry['month'].date().replace(day=1).strftime('%m.%Y'):
                entry['total_net'].quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            for entry in monthly_qs_usdt
        }

        # -----------------------
        # Чистая прибыль по месяцам (ip_income)
        # -----------------------
        monthly_ip_income = get_ip_income(
            period='months',
            start_date=start_year_date,
            end_date=end_date
        )

        deals_with_profit_months = (
            Deal.objects
            .filter(date_create__range=(start_year_date, end_date), closed=True)
            .annotate(month=TruncMonth('date_create'))
            .annotate(
                ie_usdt_expense_count=Count('deal_data', filter=Q(
                    deal_data__income_account__isnull=True,
                    deal_data__expense_account__currency__short_name='USDT'
                ), distinct=True),
                debt_writeoff_rub_count=Count('debt_operations', filter=Q(
                    debt_operations__operation_type='write_off',
                    debt_operations__currency__short_name='RUB'
                ), distinct=True),
                ie_expense_usd=Coalesce(Sum(
                    ExpressionWrapper(F('deal_data__expense_amount') * F('deal_data__expense_rate'),
                                      output_field=DecimalField()),
                    filter=Q(deal_data__income_account__isnull=True,
                             deal_data__expense_account__currency__short_name='USDT')
                ), Value(0, output_field=DecimalField())),
                debt_writeoff_rub_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
                    debt_operations__operation_type='write_off',
                    debt_operations__currency__short_name='RUB'
                )), Value(0, output_field=DecimalField())),
                debt_writeoff_non_usd_sum=Coalesce(Sum('debt_operations__amount', filter=Q(
                    debt_operations__operation_type='write_off'
                ) & ~Q(debt_operations__currency__short_name__in=['USD', 'USDT'])),
                                                   Value(0, output_field=DecimalField())),
                usdt_writeon_sum=Coalesce(Sum(
                    ExpressionWrapper(F('debt_operations__amount') * F('rate_contractors'),
                                      output_field=DecimalField()),
                    filter=Q(debt_operations__operation_type='write_on', debt_operations__currency__short_name='USDT')
                ), Value(0, output_field=DecimalField())),
            )
            .annotate(
                deal_profit=Case(
                    When(ie_usdt_expense_count=1, debt_writeoff_rub_count=1,
                         then=F('debt_writeoff_rub_sum') - F('ie_expense_usd')),
                    When(ie_usdt_expense_count=0, debt_writeoff_non_usd_sum__gt=0, usdt_writeon_sum__gt=0,
                         then=F('debt_writeoff_non_usd_sum') - F('usdt_writeon_sum')),
                    default=Value(0, output_field=DecimalField()),
                    output_field=DecimalField()
                )
            )
            .values('month', 'deal_profit')
        )

        extra_profit_months_dict = {}
        for row in deals_with_profit_months:
            # Важно: приводим к формату '01.2024'
            m_str = row['month'].date().replace(day=1).strftime('%m.%Y')
            extra_profit_months_dict[m_str] = extra_profit_months_dict.get(m_str, Decimal("0")) + (
                        row['deal_profit'] or Decimal("0"))
        # -----------------------
        # Все ключи месяцев (аналогично дням)
        # -----------------------
        all_months = set()
        all_months |= set(extra_profit_months_dict.keys())
        all_months |= set(monthly_net.keys())
        all_months |= set(monthly_net_usd.keys())
        all_months |= set(monthly_net_usdt.keys())
        all_months |= set(nikita_monthly.keys())
        all_months |= set(monthly_usd_commission.keys())
        all_months |= set(monthly_ip_income.keys())
        all_months.add(today.strftime('%m.%Y'))  # на всякий случай добавляем текущий месяц

        all_months = sorted(all_months, key=lambda d: datetime.datetime.strptime(d, '%m.%Y'))

        # -----------------------
        # Формируем итоговый список
        # -----------------------
        monthly_combined = [
            (
                month,
                (monthly_net.get(month, Decimal("0.000")) + monthly_ip_income.get(month, Decimal("0.000")) + extra_profit_months_dict.get(month, Decimal("0.000"))).quantize(
                    Decimal("0.001"), rounding=ROUND_HALF_UP),
                monthly_net_usd.get(month, (Decimal("0.000"), Decimal("0.000")))[0].quantize(Decimal("0.001"),
                                                                                             rounding=ROUND_HALF_UP),
                monthly_usd_commission.get(month, Decimal("0.000")),
                monthly_net_usdt.get(month, Decimal("0.000")),
                nikita_monthly.get(month, Decimal("0.000")),
                monthly_ip_income.get(month, Decimal("0.000"))
            )
            for month in all_months
        ]

        return monthly_combined



def get_marginality():
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    results = []
    for single_day in days:
        ids = list(
            IncomeExpense.objects
            .filter(date_create__date=single_day)
            .values_list('id', flat=True)
        )
        day_name = single_day.strftime('%A').lower()
        results.append({
            'day': day_name,
            'ids': ids
        })
    x = []
    y = []
    for result in results:
        x.append(result['day'])
        margin_day = 0
        in_exes = IncomeExpense.objects.filter(id__in=result['ids'])
        for in_ex in in_exes:
            if in_ex.income_account and in_ex.expense_account:
                if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                    income = in_ex.income_amount * in_ex.income_rate
                else:
                    income = in_ex.income_amount
                if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense = in_ex.expense_amount * in_ex.expense_rate
                else:
                    expense = in_ex.expense_amount
            elif in_ex.income_account and  not in_ex.expense_account:
                if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                    income = in_ex.income_amount * in_ex.income_rate
                else:
                    income = in_ex.income_amount
                expense = 0
            elif in_ex.expense_account and not in_ex.income_account:
                if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense = in_ex.expense_amount * in_ex.expense_rate
                else:
                    expense = in_ex.expense_amount
                income = 0
            try:
                margin_pct = (income - expense) / income * 100
            except:
                margin_pct = 0
            margin_day += margin_pct
        try:
            margin_proc = round(margin_day / in_exes.count())
        except:
            margin_proc = 0
        y.append(float(margin_proc))
    return x, y

def get_dds_list():
    ddses = CashFlow.objects.all()
    x = []
    y = []



def get_dds():
    twelve_months_ago = now() - timedelta(days=365)
    qs = (
        IncomeExpense.objects
        .filter(date_create__gte=twelve_months_ago)
        .annotate(month=TruncMonth('date_create'))
        .values('id', 'month')
    )
    grouped = defaultdict(list)
    for entry in qs:
        month_num = entry['month'].month
        month_name = calendar.month_name[month_num].lower()
        grouped[month_name].append(entry['id'])
    results = [{'month': month, 'ids': ids} for month, ids in grouped.items()]
    x = []
    y = []
    for result in results:
        x.append(result['month'])
        dds_month = 0
        in_exes = IncomeExpense.objects.filter(id__in=result['ids'], deal__cashflow__isnull=False)
        for in_ex in in_exes:
            if in_ex.income_account and in_ex.expense_account:
                if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                    income = in_ex.income_amount * in_ex.income_rate
                else:
                    income = in_ex.income_amount
                if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense = in_ex.expense_amount * in_ex.expense_rate
                else:
                    expense = in_ex.expense_amount
            elif in_ex.income_account and  not in_ex.expense_account:
                if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                    income = in_ex.income_amount * in_ex.income_rate
                else:
                    income = in_ex.income_amount
                expense = 0
            elif in_ex.expense_account and not in_ex.income_account:
                if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense = in_ex.expense_amount * in_ex.expense_rate
                else:
                    expense = in_ex.expense_amount
                income = 0
            dds_month += (income - expense)
        y.append(float(dds_month))
    return x, y

def get_total_profit_by_week():
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    results = []
    for single_day in days:
        ids = list(
            IncomeExpense.objects
            .filter(date_create__date=single_day)
            .values_list('id', flat=True)
        )
        day_name = single_day.strftime('%A').lower()
        results.append({
            'day': day_name,
            'ids': ids
        })
    x = []
    y = []
    for result in results:
        x.append(result['day'])
        profit_day = 0
        in_exes = IncomeExpense.objects.filter(id__in=result['ids'])
        for in_ex in in_exes:
            if in_ex.income_account and in_ex.expense_account:
                if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                    income = in_ex.income_amount * in_ex.income_rate
                else:
                    income = in_ex.income_amount
                if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense = in_ex.expense_amount * in_ex.expense_rate
                else:
                    expense = in_ex.expense_amount
            elif in_ex.income_account and not in_ex.expense_account:
                if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                    income = in_ex.income_amount * in_ex.income_rate
                else:
                    income = in_ex.income_amount
                expense = 0
            elif in_ex.expense_account and not in_ex.income_account:
                if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense = in_ex.expense_amount * in_ex.expense_rate
                else:
                    expense = in_ex.expense_amount
                income = 0
            try:
                profit = (income/expense) * 100
            except:
                profit = 0
            profit_day += profit
        y.append(float(profit_day))
    return x, y

def get_total_profit_by_year():
    twelve_months_ago = now() - timedelta(days=365)
    qs = (
        IncomeExpense.objects
        .filter(date_create__gte=twelve_months_ago)
        .annotate(month=TruncMonth('date_create'))
        .values('id', 'month')
    )
    grouped = defaultdict(list)
    for entry in qs:
        month_num = entry['month'].month
        month_name = calendar.month_name[month_num].lower()
        grouped[month_name].append(entry['id'])
    results = [{'month': month, 'ids': ids} for month, ids in grouped.items()]
    x = []
    y = []
    for result in results:
        x.append(result['month'])
        profit_month = 0
        in_exes = IncomeExpense.objects.filter(id__in=result['ids'])
        for in_ex in in_exes:
            if in_ex.income_account and in_ex.expense_account:
                if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                    income = in_ex.income_amount * in_ex.income_rate
                else:
                    income = in_ex.income_amount
                if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense = in_ex.expense_amount * in_ex.expense_rate
                else:
                    expense = in_ex.expense_amount
            elif in_ex.income_account and not in_ex.expense_account:
                if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                    income = in_ex.income_amount * in_ex.income_rate
                else:
                    income = in_ex.income_amount
                expense = 0
            elif in_ex.expense_account and not in_ex.income_account:
                if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense = in_ex.expense_amount * in_ex.expense_rate
                else:
                    expense = in_ex.expense_amount
                income = 0
            try:
                profit = (income/expense) * 100
            except:
                profit = 0
            profit_month += profit
        y.append(float(profit_month))
    return x, y


def get_changes_of_rates():
    twelve_months_ago = now() - timedelta(days=365)
    qs = (
        IncomeExpense.objects
        .filter(date_create__gte=twelve_months_ago)
        .annotate(month=TruncMonth('date_create'))
        .values('id', 'month')
    )
    grouped = defaultdict(list)
    for entry in qs:
        month_num = entry['month'].month
        month_name = calendar.month_name[month_num].lower()
        grouped[month_name].append(entry['id'])
    results = [{'month': month, 'ids': ids} for month, ids in grouped.items()]
    x_usdt = []
    y_usdt = []
    x_usd = []
    y_usd = []
    for result in results:
        x_usdt.append(result['month'])
        in_exes = IncomeExpense.objects.filter(id__in=result['ids'], income_account__currency__short_name='USDT')
        try:
            first_rate = in_exes.first().deal.deal_course.first().rate_old
            last_rate = in_exes.last().deal.deal_course.first().rate_new
            rate_proc = ((first_rate - last_rate)/first_rate) * 100
            y_usdt.append(float(rate_proc))
        except:
            y_usdt.append(0)
        x_usd.append(result['month'])
        in_exes = IncomeExpense.objects.filter(id__in=result['ids'], income_account__currency__short_name='USD')
        try:
            first_rate = in_exes.first().deal.deal_course.first().rate_old
            last_rate = in_exes.last().deal.deal_course.first().rate_new
            rate_proc = ((first_rate - last_rate) / first_rate) * 100
            y_usd.append(float(rate_proc))
        except:
            y_usd.append(0)
    return x_usdt, y_usdt, x_usd, y_usd

def get_count_deals():
    today = timezone.localdate()
    start_date = today - timedelta(days=7)

    qs = (
        IncomeExpense.objects
        .filter(
            date_create__date__gte=start_date,
            date_create__date__lt=today  # вместо lte — только до вчера
        )
        .annotate(dow=ExtractWeekDay('date_create'))
        .values('dow')
        .annotate(count=Count('id'))
        .order_by('dow')
    )

    # 1=воскресенье … 7=суббота
    DAY_NAMES = {
        1: 'воскресенье',
        2: 'понедельник',
        3: 'вторник',
        4: 'среда',
        5: 'четверг',
        6: 'пятница',
        7: 'суббота',
    }

    counts = {item['dow']: item['count'] for item in qs}
    x = []
    y = []

    # Проходим по интервалу [today-7 … сегодня-1]
    for delta in range(7, 0, -1):
        day = today - timedelta(days=delta)
        extract_dow = (day.isoweekday() % 7) + 1
        x.append(DAY_NAMES[extract_dow])
        y.append(counts.get(extract_dow, 0))

    return x, y

def get_all_in_ex_by_currency():
    in_usdt = IncomeExpense.objects.filter(income_account__currency__short_name='USDT').aggregate(total_income=Sum('income_amount'))['total_income'] or 0
    ex_usdt = IncomeExpense.objects.filter(expense_account__currency__short_name='USDT').aggregate(
        total_expense=Sum('expense_amount'))['total_expense'] or 0
    in_usd = IncomeExpense.objects.filter(income_account__currency__short_name='USD').aggregate(
        total_income=Sum('income_amount'))['total_income'] or 0
    ex_usd = IncomeExpense.objects.filter(expense_account__currency__short_name='USD').aggregate(
        total_expense=Sum('expense_amount'))['total_expense'] or 0
    in_nas = IncomeExpense.objects.filter(income_account__currency__short_name='RUB').aggregate(
        total_income=Sum('income_amount'))['total_income'] or 0
    ex_nas = IncomeExpense.objects.filter(expense_account__currency__short_name='RUB').aggregate(
        total_expense=Sum('expense_amount'))['total_expense'] or 0
    y = [float(in_usdt), float(ex_usdt), float(in_usd), float(ex_usd), float(in_nas), float(ex_nas)]
    x = ['USDT', 'USDT', 'USD', 'USD', 'RUB', 'RUB']
    return x, y
    #return  [{'currency': 'USDT', 'income': in_usdt, 'expense': ex_usdt}, {'currency': 'USD', 'income': in_usd, 'expense': ex_usd}, {'currency': 'RUB', 'income': in_nas, 'expense': ex_nas}]
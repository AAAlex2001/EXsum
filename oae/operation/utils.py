from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q, OuterRef, Exists,Count
from decimal import Decimal
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.db import transaction
from catalog.models import Contractor, Bill
from operation.models import IncomeExpense, Deal, DealRepayment, ContractorDebtOperation




@transaction.atomic
def apply_ie_fifo(
    contractor,
    from_date=None,
    force_recalc=False
):
    """
    Инкрементальный FIFO по доходам/расходам контрагента.
    НИЧЕГО не пересчитывает заново, а продолжает очередь.

    from_date=None        → применить ко всем доходам
    from_date=date        → применить только к новым доходам
    force_recalc=True     → полный сброс (аварийный режим)
    """

    # =====================================================
    # 0. Полный сброс (если принудительно)
    # =====================================================
    if force_recalc:
        DealRepayment.objects.filter(
            calc__contractor=contractor
        ).delete()

        Deal.objects.filter(
            contractor=contractor
        ).update(
            amount_repaid=Decimal('0'),
            is_repaid=False,
            status_ie=Deal.STATUS.DEFAULT
        )

    # =====================================================
    # 1. Начальный долг контрагента
    # =====================================================
    contractor_duty_total = contractor.duty

    contractor_duty_repaid = (
        DealRepayment.objects
        .filter(
            contractor_duty=True,
            calc__contractor=contractor
        )
        .aggregate(s=Sum('amount'))['s']
        or Decimal('0')
    )

    # =====================================================
    # 2. Очередь расходов (ТОЛЬКО непогашенные)
    # =====================================================
    expense_deals = list(
        Deal.objects.filter(
            contractor=contractor,
            closed=True,
            is_repaid=False
        ).order_by('date_create')
    )

    # =====================================================
    # 3. Доходные сделки
    # =====================================================
    incomes = Deal.objects.filter(
        contractor=contractor,
        closed=True,
        deal_data__expense_account__isnull=True
    ).order_by('date_create')

    if from_date:
        incomes = incomes.filter(date_create__gte=from_date)

    # =====================================================
    # 4. FIFO
    # =====================================================
    for income in incomes:

        in_ex = IncomeExpense.objects.filter(deal=income).first()
        if not in_ex or not in_ex.income_account:
            continue

        # ---- сумма дохода ----
        if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
            income_total = in_ex.income_amount * in_ex.income_rate
        else:
            income_total = in_ex.income_amount

        # ---- сколько уже использовано этим доходом ----
        used = (
            DealRepayment.objects
            .filter(calc=income)
            .aggregate(s=Sum('amount'))['s']
            or Decimal('0')
        )

        remainder = income_total - used
        if remainder <= 0:
            continue

        # =================================================
        # 4.1 Гасим начальный долг контрагента
        # =================================================
        if contractor_duty_repaid < contractor_duty_total:
            need = contractor_duty_total - contractor_duty_repaid
            pay = min(need, remainder)

            if pay > 0 and not DealRepayment.objects.filter(
                calc=income,
                contractor_duty=True
            ).exists():
                DealRepayment.objects.create(
                    calc=income,
                    contractor_duty=True,
                    amount=pay,
                    date_create=income.date_create
                )

                contractor_duty_repaid += pay
                remainder -= pay

        # =================================================
        # 4.2 FIFO расходов
        # =================================================
        for expense in expense_deals:
            if remainder <= 0:
                break

            # доход не может дважды гасить одну сделку
            if DealRepayment.objects.filter(
                calc=income,
                duty=expense
            ).exists():
                continue

            ex = expense.deal_data.first() if expense.deal_data.exists() else None

            if ex:
                if ex.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense_total = ex.expense_amount * expense.rate
                else:
                    expense_total = ex.expense_amount
            else:
                expense_total = expense.duty_deal

            need = expense_total - expense.amount_repaid
            if need <= 0:
                continue

            pay = min(need, remainder)
            if pay <= 0:
                continue

            DealRepayment.objects.create(
                calc=income,
                duty=expense,
                amount=pay,
                date_create=income.date_create
            )

            expense.amount_repaid += pay
            remainder -= pay

            if expense.amount_repaid >= expense_total:
                expense.is_repaid = True
                expense.status_ie = Deal.STATUS.REPAID
            else:
                expense.status_ie = Deal.STATUS.DUTY

            expense.save(
                update_fields=['amount_repaid', 'is_repaid', 'status_ie']
            )

        # =================================================
        # 4.3 Статус дохода
        # =================================================
        income.status_ie = (
            Deal.STATUS.REPAID if remainder == 0 else Deal.STATUS.DUTY
        )
        income.save(update_fields=['status_ie'])

def deal_amount(deal):
    ie = deal.deal_data.first()
    if not ie:
        return Decimal('0')

    if deal.status_ie == Deal.STATUS.DUTY:
        if ie.expense_account and ie.expense_account.currency.short_name in ['USD', 'USDT']:
            return ie.expense_amount * deal.rate
        return ie.expense_amount or Decimal('0')

    if ie.income_account and ie.income_account.currency.short_name in ['USD', 'USDT']:
        return ie.income_amount * ie.income_rate
    return ie.income_amount or Decimal('0')

def detect_status_ie(deal):
    """
    Определяет статус IE по IncomeExpense.
    Возвращает Deal.STATUS.DUTY / REPAID / DEFAULT
    """
    from operation.models import Deal, DealRepayment, IncomeExpense
    ies = deal.deal_data.all()

    has_income = ies.filter(income_account__isnull=False).exists()
    has_expense = ies.filter(expense_account__isnull=False).exists()

    if has_expense and not has_income:
        return Deal.STATUS.DUTY

    if has_income and not has_expense:
        return Deal.STATUS.REPAID

    return Deal.STATUS.DEFAULT

def apply_calc_to_existing_duties(calc):
    from django.db import transaction
    from django.db.models import Sum
    from operation.models import Deal, DealRepayment, IncomeExpense
    with transaction.atomic():
        calc_total = deal_amount(calc)

        duties = (
            Deal.objects
            .select_for_update()
            .filter(
                contractor=calc.contractor,
                status_ie=Deal.STATUS.DUTY,
                is_repaid=False
            )
            .order_by('date_create')
        )

        for duty in duties:
            debt_left = deal_amount(duty) - (duty.amount_repaid or Decimal('0'))
            if debt_left <= 0:
                continue

            used = DealRepayment.objects.filter(calc=calc).aggregate(
                s=Sum('amount')
            )['s'] or Decimal('0')

            available = calc_total - used
            if available <= 0:
                break

            pay_amount = min(available, debt_left)

            DealRepayment.objects.create(
                duty=duty,
                calc=calc,
                amount=pay_amount
            )

            duty.amount_repaid += pay_amount

            if duty.amount_repaid >= deal_amount(duty):
                duty.is_repaid = True

            duty.save(update_fields=['amount_repaid', 'is_repaid'])


def apply_calcs_to_new_duty(duty):
    from django.db import transaction
    from django.db.models import Sum
    from operation.models import Deal, DealRepayment, IncomeExpense
    with transaction.atomic():
        duty_total = deal_amount(duty)
        debt_left = duty_total - (duty.amount_repaid or Decimal('0'))

        calcs = (
            Deal.objects
            .select_for_update()
            .filter(
                contractor=duty.contractor,
                status_ie=Deal.STATUS.REPAID
            )
            .order_by('date_create')
        )

        for calc in calcs:
            used = DealRepayment.objects.filter(calc=calc).aggregate(
                s=Sum('amount')
            )['s'] or Decimal('0')

            available = deal_amount(calc) - used
            if available <= 0:
                continue

            pay_amount = min(available, debt_left)

            DealRepayment.objects.create(
                duty=duty,
                calc=calc,
                amount=pay_amount
            )

            duty.amount_repaid += pay_amount
            debt_left -= pay_amount

            if debt_left <= 0:
                duty.is_repaid = True
                break

        duty.save(update_fields=['amount_repaid', 'is_repaid'])

def calculate_duty_repaid(contractor):
    from operation.models import Deal, DealRepayment

    duties = (
        Deal.objects
        .select_for_update()
        .filter(
            contractor=contractor,
            status_ie=Deal.STATUS.DUTY,
            is_repaid=False
        )
        .order_by('date_create')
        .prefetch_related('deal_data')
    )

    calcs = (
        Deal.objects
        .select_for_update()
        .filter(
            contractor=contractor,
            status_ie=Deal.STATUS.REPAID
        )
        .order_by('date_create')
        .prefetch_related('deal_data')
    )

    calcs = list(calcs)
    calc_index = 0
    calc_remainder = Decimal('0')

    def deal_amount(deal):
        ie = deal.deal_data.first()
        if not ie:
            return Decimal('0')

        if deal.status_ie == Deal.STATUS.DUTY:
            if ie.expense_account and ie.expense_account.currency.short_name in ['USD', 'USDT']:
                return ie.expense_amount * (deal.rate or Decimal('1'))
            return ie.expense_amount or Decimal('0')

        if ie.income_account and ie.income_account.currency.short_name in ['USD', 'USDT']:
            return ie.income_amount * (ie.income_rate or Decimal('1'))

        return ie.income_amount or Decimal('0')

    for duty in duties:
        debt_left = deal_amount(duty)

        while debt_left > 0 and calc_index < len(calcs):
            calc = calcs[calc_index]

            available = calc_remainder or deal_amount(calc)
            pay_amount = min(available, debt_left)

            DealRepayment.objects.create(
                duty=duty,
                calc=calc,
                amount=pay_amount
            )

            debt_left -= pay_amount
            duty.amount_repaid += pay_amount

            if available > pay_amount:
                calc_remainder = available - pay_amount
            else:
                calc_remainder = Decimal('0')
                calc_index += 1

        if debt_left <= 0:
            duty.is_repaid = True

        duty.save(update_fields=['amount_repaid', 'is_repaid'])

def apply_ie_statuses(contractor):
    from operation.models import Deal

    deals = (
        Deal.objects
        .filter(contractor=contractor)
        .exclude(status_ie=Deal.STATUS.OPENING_DUTY)
        .prefetch_related('deal_data')
    )

    for deal in deals:
        ie = deal.deal_data.first()
        if not ie:
            continue

        has_expense = ie.expense_amount and ie.expense_amount > 0
        has_income = ie.income_amount and ie.income_amount > 0

        if has_expense and not has_income:
            deal.status_ie = Deal.STATUS.DUTY

        elif has_income and not has_expense:
            deal.status_ie = Deal.STATUS.REPAID

        else:
            continue

        deal.save(update_fields=['status_ie'])



def reset_calculations(contractor):
    from operation.models import Deal, DealRepayment

    DealRepayment.objects.filter(
        duty__contractor=contractor
    ).delete()

    Deal.objects.filter(contractor=contractor).update(
        amount_repaid=Decimal('0'),
        is_repaid=False
    )

def make_ie_calculate_full_v5():
    from catalog.models import Contractor
    from operation.models import Deal, DealRepayment, IncomeExpense
    from decimal import Decimal

    contractor = Contractor.objects.get(id=1)

    # 0️⃣ Очистка старых расчетов
    DealRepayment.objects.all().delete()

    # 1️⃣ Сброс сделок
    Deal.objects.filter(contractor=contractor).update(
        is_repaid=False,
        by_ie=True,
        amount_repaid=Decimal('0'),
        status_ie=Deal.STATUS.DEFAULT
    )

    # 2️⃣ Начальный долг
    opening_duty_remainder = contractor.duty or Decimal('0')

    # 3️⃣ Все доходные сделки
    income_deals = (
        Deal.objects
        .filter(contractor=contractor, deal_data__expense_account__isnull=True)
        .order_by('date_create')
    )

    # 4️⃣ Гашение начального долга
    for income_deal in income_deals:
        ie = income_deal.deal_data.first()
        if not ie or not ie.income_account:
            continue

        income_total = ie.income_amount * ie.income_rate if ie.income_account.currency.short_name in ['USD', 'USDT'] else ie.income_amount
        available = income_total - (income_deal.amount_repaid or Decimal('0'))

        if opening_duty_remainder <= 0 or available <= 0:
            continue

        pay = min(available, opening_duty_remainder)
        DealRepayment.objects.create(
            calc=income_deal,
            contractor_duty=True,
            amount=pay
        )

        income_deal.amount_repaid += pay
        income_deal.status_ie = Deal.STATUS.OPENING_DUTY
        income_deal.save()

        opening_duty_remainder -= pay

    # 5️⃣ Все расходные сделки
    expense_deals = (
        Deal.objects
        .filter(contractor=contractor, deal_data__income_account__isnull=True)
        .order_by('date_create')
    )

    # 6️⃣ Распределение доходов на расходы
    for expense_deal in expense_deals:
        ie_exp = expense_deal.deal_data.first()
        if not ie_exp or not ie_exp.expense_account:
            continue

        expense_total = ie_exp.expense_amount * expense_deal.rate if ie_exp.expense_account.currency.short_name in ['USD', 'USDT'] else ie_exp.expense_amount
        expense_remainder = expense_total

        for income_deal in income_deals:
            ie_inc = income_deal.deal_data.first()
            if not ie_inc or not ie_inc.income_account:
                continue

            income_total = ie_inc.income_amount * ie_inc.income_rate if ie_inc.income_account.currency.short_name in ['USD', 'USDT'] else ie_inc.income_amount
            available = income_total - (income_deal.amount_repaid or Decimal('0'))
            if available <= 0:
                continue

            pay = min(available, expense_remainder)
            DealRepayment.objects.create(
                calc=income_deal,
                duty=expense_deal,
                amount=pay
            )

            income_deal.amount_repaid += pay
            income_deal.save()

            expense_remainder -= pay
            if expense_remainder <= 0:
                expense_deal.amount_repaid = expense_total
                expense_deal.is_repaid = True
                expense_deal.status_ie = Deal.STATUS.REPAID
                expense_deal.save()
                break

        # Остаток долга
        if expense_remainder > 0:
            expense_deal.amount_repaid = expense_total - expense_remainder
            expense_deal.status_ie = Deal.STATUS.DUTY
            expense_deal.save()

    # 7️⃣ Финальная расстановка статусов доходных сделок
    for income_deal in income_deals:
        ie = income_deal.deal_data.first()
        if not ie or not ie.income_account:
            continue

        income_total = ie.income_amount * ie.income_rate if ie.income_account.currency.short_name in ['USD', 'USDT'] else ie.income_amount
        used = income_deal.amount_repaid or Decimal('0')

        has_opening = income_deal.repayments.filter(contractor_duty=True).exists()
        has_expense = income_deal.repayments.filter(duty__isnull=False).exists()

        if has_opening and not has_expense:
            income_deal.status_ie = Deal.STATUS.OPENING_DUTY
        elif has_expense and used >= income_total:
            income_deal.status_ie = Deal.STATUS.REPAID
        else:
            income_deal.status_ie = Deal.STATUS.DEFAULT

        income_deal.save()


def make_ie_calculate_full_v4():
    from catalog.models import Contractor
    from decimal import Decimal

    contractor = Contractor.objects.get(id=1)

    # 0. Очистка старых расчётов
    DealRepayment.objects.all().delete()

    # 1. Сброс сделок
    Deal.objects.filter(contractor=contractor).update(
        is_repaid=False,
        by_ie=True,
        amount_repaid=Decimal('0'),
        status_ie=Deal.STATUS.DEFAULT
    )

    # ======================================================
    # 2. НАЧАЛЬНЫЙ ДОЛГ
    # ======================================================

    opening_duty_remainder = contractor.duty or Decimal('0')

    # ======================================================
    # 3. ДОХОДЫ (FIFO)
    # ======================================================

    income_deals = (
        Deal.objects
        .filter(contractor=contractor, deal_data__expense_account__isnull=True)
        .order_by('date_create')
    )

    # ======================================================
    # 4. ГАСИМ НАЧАЛЬНЫЙ ДОЛГ
    # ======================================================

    for income_deal in income_deals:

        if opening_duty_remainder <= 0:
            break

        ie = income_deal.deal_data.first()
        if not ie or not ie.income_account:
            continue

        if ie.income_account.currency.short_name in ['USD', 'USDT']:
            income_total = ie.income_amount * ie.income_rate
        else:
            income_total = ie.income_amount

        already_used = income_deal.amount_repaid or Decimal('0')
        available = income_total - already_used

        if available <= 0:
            continue

        # полностью уходит в начальный долг
        if available <= opening_duty_remainder:
            DealRepayment.objects.create(
                calc=income_deal,
                contractor_duty=True,
                amount=available
            )

            income_deal.amount_repaid += available
            income_deal.status_ie = Deal.STATUS.OPENING_DUTY
            income_deal.save()

            opening_duty_remainder -= available

        # закрывает остаток начального долга
        else:
            DealRepayment.objects.create(
                calc=income_deal,
                contractor_duty=True,
                amount=opening_duty_remainder
            )

            income_deal.amount_repaid += opening_duty_remainder
            income_deal.status_ie = Deal.STATUS.OPENING_DUTY
            income_deal.save()

            opening_duty_remainder = Decimal('0')
            break  # остаток дохода пойдёт на расходы

    # ======================================================
    # 5. РАСХОДЫ (СОЗДАЮТ ДОЛГ)
    # ======================================================

    expense_deals = (
        Deal.objects
        .filter(contractor=contractor, deal_data__income_account__isnull=True)
        .order_by('date_create')
    )

    # ======================================================
    # 6. ГАСИМ РАСХОДЫ ДОХОДАМИ
    # ======================================================

    for expense_deal in expense_deals:

        ie_exp = expense_deal.deal_data.first()
        if not ie_exp or not ie_exp.expense_account:
            continue

        if ie_exp.expense_account.currency.short_name in ['USD', 'USDT']:
            expense_total = ie_exp.expense_amount * expense_deal.rate
        else:
            expense_total = ie_exp.expense_amount

        expense_remainder = expense_total

        income_sources = (
            Deal.objects
            .filter(contractor=contractor, deal_data__expense_account__isnull=True)
            .order_by('date_create')
        )

        for income_deal in income_sources:

            ie_inc = income_deal.deal_data.first()
            if not ie_inc or not ie_inc.income_account:
                continue

            if ie_inc.income_account.currency.short_name in ['USD', 'USDT']:
                income_total = ie_inc.income_amount * ie_inc.income_rate
            else:
                income_total = ie_inc.income_amount

            used = income_deal.amount_repaid or Decimal('0')
            available = income_total - used

            if available <= 0:
                continue

            # частичное погашение
            if available < expense_remainder:
                DealRepayment.objects.create(
                    calc=income_deal,
                    duty=expense_deal,
                    amount=available
                )

                income_deal.amount_repaid += available
                income_deal.save()

                expense_remainder -= available

            # полное погашение
            else:
                DealRepayment.objects.create(
                    calc=income_deal,
                    duty=expense_deal,
                    amount=expense_remainder
                )

                income_deal.amount_repaid += expense_remainder
                income_deal.save()

                expense_deal.amount_repaid = expense_total
                expense_deal.is_repaid = True
                expense_deal.status_ie = Deal.STATUS.REPAID
                expense_deal.save()

                expense_remainder = Decimal('0')
                break

        # если остался долг
        if expense_remainder > 0:
            expense_deal.amount_repaid = expense_total - expense_remainder
            expense_deal.status_ie = Deal.STATUS.DUTY
            expense_deal.save()

    # ======================================================
    # 7. ФИНАЛЬНАЯ РАССТАНОВКА СТАТУСОВ ДОХОДОВ
    # ======================================================

    for income_deal in income_deals:

        ie = income_deal.deal_data.first()
        if not ie or not ie.income_account:
            continue

        if ie.income_account.currency.short_name in ['USD', 'USDT']:
            income_total = ie.income_amount * ie.income_rate
        else:
            income_total = ie.income_amount

        used = income_deal.amount_repaid or Decimal('0')

        has_opening = income_deal.repayments.filter(contractor_duty=True).exists()
        has_expense = income_deal.repayments.filter(duty__isnull=False).exists()

        # только начальный долг
        if has_opening and not has_expense:
            income_deal.status_ie = Deal.STATUS.OPENING_DUTY

        # участвовал в расходах и исчерпан
        elif has_expense and used >= income_total:
            income_deal.status_ie = Deal.STATUS.REPAID

        # иначе — есть остаток
        else:
            income_deal.status_ie = Deal.STATUS.DEFAULT

        income_deal.save()









def make_ie_calculate_full_v3():
    from catalog.models import Contractor
    from operation.models import Deal, DealRepayment, IncomeExpense, ContractorDebtOperation

    # очистка старых расчетов
    DealRepayment.objects.all().delete()

    contractor = Contractor.objects.get(id=1)

    # сброс флагов
    Deal.objects.filter(contractor=contractor).update(
        is_repaid=False,
        by_ie=True,
        amount_repaid=0,
        status_ie=0
    )

    # начальный долг контрагента
    contractor_duty_total = abs(contractor.duty)
    contractor_duty_repaid = 0

    # ===== Сбор всех расходных сделок =====
    expense_deals = list(
        Deal.objects.filter(contractor=contractor, closed=True)
        .filter(deal_data__income_account__isnull=True)
        .order_by('date_create')
    )

    # ===== Добавляем сделки без IncomeExpense, но с duty_deal =====
    duty_only_deals = list(
        Deal.objects.filter(contractor=contractor, closed=True)
        .filter(deal_data__isnull=True, duty_deal__isnull=False)
        .order_by('date_create')
    )

    # Объединяем все расходные сделки и сортируем по дате

    all_expense_deals = list({d.id: d for d in list(expense_deals) + list(duty_only_deals)}.values())
    all_expense_deals.sort(key=lambda d: d.date_create)

    # ===== Сбор всех приходов =====
    income_deals_normal = Deal.objects.filter(
        contractor=contractor,
        deal_data__expense_account__isnull=True,
        closed=True,
        status_ie=0
    )

    # сделки с ContractorDebtOperation (write_on, RUB)
    debt_deals = Deal.objects.filter(
        debt_operations__contractor=contractor,
        debt_operations__operation_type='write_on',
        debt_operations__currency__short_name='RUB'
    ).distinct()

    # объединяем через union и сортируем по дате
    income_deals = income_deals_normal.union(debt_deals).order_by('date_create')

    for income_deal in income_deals:
        # Получаем сумму прихода
        try:
            in_exes = IncomeExpense.objects.filter(deal=income_deal)
            debts = ContractorDebtOperation.objects.filter(deal=income_deal, contractor=contractor)
            remainder = 0
            if in_exes.count() != 0 :
                for in_ex in in_exes:
                    if in_ex.income_account:
                        if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                            remainder += in_ex.income_amount * in_ex.income_rate
                        else:
                            remainder += in_ex.income_amount
            elif debts.count() != 0:
                for debt in debts:
                    remainder += debt.amount
            else:
                continue
        except:
            remainder = 0

        # ===== 1. Гасим начальный долг =====
        if contractor.duty < 0 and contractor_duty_repaid < contractor_duty_total and remainder > 0:
            need = contractor_duty_total - contractor_duty_repaid
            pay = min(need, remainder)
            if pay > 0:
                DealRepayment.objects.create(
                    calc=income_deal,
                    contractor_duty=True,
                    amount=pay,
                    date_create=income_deal.date_create
                )
            contractor_duty_repaid += pay
            remainder -= pay
            income_deal.status_ie = 2 if contractor_duty_repaid == contractor_duty_total else 3
            income_deal.save()

        # ===== 2. Гасим все расходные сделки FIFO =====
        for expense_deal in all_expense_deals:
            if remainder <= 0:
                break

            # Проверяем, есть ли уже погашение для этого дохода и расхода
            if DealRepayment.objects.filter(calc=income_deal, duty=expense_deal).exists():
                continue

            # Получаем сумму расходной сделки
            in_ex_exp = expense_deal.deal_data.first() if expense_deal.deal_data.exists() else None
            if in_ex_exp:
                if in_ex_exp.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense_amount = in_ex_exp.expense_amount * expense_deal.rate
                else:
                    expense_amount = in_ex_exp.expense_amount
            elif getattr(expense_deal, 'duty_deal', None):
                expense_amount = expense_deal.duty_deal
            else:
                continue

            already_repaid = expense_deal.amount_repaid or 0
            need = expense_amount - already_repaid
            if need <= 0:
                continue

            pay = min(need, remainder)
            if pay > 0:
                DealRepayment.objects.create(
                    calc=income_deal,
                    duty=expense_deal,
                    amount=pay,
                    date_create=income_deal.date_create
                )

            # Обновляем статус расходной сделки
            expense_deal.amount_repaid = already_repaid + pay
            if expense_deal.amount_repaid >= expense_amount:
                expense_deal.is_repaid = True
                expense_deal.status_ie = 2
            else:
                expense_deal.status_ie = 1
            expense_deal.save()

            remainder -= pay

        # Если приход полностью распределен
        if remainder == 0:
            income_deal.status_ie = 3
            income_deal.save()



def make_ie_calculate_full_v2():
    from catalog.models import Contractor
    DealRepayment.objects.all().delete()
    contractor_id = 1
    contractor = Contractor.objects.get(id=contractor_id)
    deals = Deal.objects.filter(contractor=contractor).order_by('date_create')
    deals.update(is_repaid=False, by_ie=True, amount_repaid=None, status_ie=0)
    contractor_duty = contractor.duty
    total_contractor_duty = 0
    remainder_contractor_duty = 0
    deals_income = Deal.objects.filter(contractor=contractor, deal_data__expense_account__isnull=True, status_ie=0)
    for deal in deals_income:
        if contractor_duty >= total_contractor_duty:
            try:
                in_ex = IncomeExpense.objects.get(deal=deal)
            except:
                print(deal.id)
            if in_ex.income_account and not in_ex.expense_amount:
                if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                    income = in_ex.income_amount * in_ex.income_rate
                else:
                    income = in_ex.income_amount
                if total_contractor_duty + income < contractor_duty:
                    total_contractor_duty += income
                    deal.status_ie = 3
                    deal.save()
                    deal_r = DealRepayment(calc=deal, contractor_duty=True, amount=income)
                    deal_r.save()
                else:
                    remainder_contractor_duty = total_contractor_duty + income - contractor_duty
                    total_contractor_duty = contractor_duty
                    deal.status_ie = 2
                    deal.save()
                    deal_r = DealRepayment(calc=deal, contractor_duty=True, amount=contractor_duty - total_contractor_duty)
                    deal_r.save()
                    deal_expense = Deal.objects.filter(contractor=contractor, deal_data__income_account__isnull=True,amount_repaid=None).first()
                    if deal_expense.deal_data.first().expense_account.currency.short_name in ['USD', 'USDT']:
                        expense = deal_expense.deal_data.first().expense_amount * deal_expense.rate
                    else:
                        expense = deal_expense.deal_data.first().expense_amount
                    if expense > remainder_contractor_duty:
                        deal_r = DealRepayment(calc=deal, duty=deal_expense, amount=remainder_contractor_duty)
                        deal_r.save()
                        deal_expense.stasus_ie = 1
                        deal.amount_repaid = remainder_contractor_duty
                        deal.save()
        else:
            break
    deals_expense = Deal.objects.filter(contractor=contractor, deal_data__income_account__isnull=True)
    for deal in deals_expense:
        if deal.amount_repaid:
            if deal.deal_data.first().expense_account.currency.short_name in ['USD', 'USDT']:
                expense = deal.deal_data.first().expense_amount * deal.rate - deal.amount_repaid
            else:
                expense = deal.deal_data.first().expense_amount - deal.amount_repaid
        else:
            if deal.deal_data.first().expense_account.currency.short_name in ['USD', 'USDT']:
                expense = deal.deal_data.first().expense_amount * deal.rate
            else:
                expense = deal.deal_data.first().expense_amount
        deals_income = Deal.objects.filter(contractor=contractor, deal_data__expense_account__isnull=True, status_ie=0)
        remainder = 0
        for deal_income in deals_income:
            if remainder != 0:
                income = remainder
                deal.status_ie = 2
                deal.amount_repaid = income
                deal.save()
                deal_income.status_ie = 3
                deal_income.save()
                deal_r = DealRepayment(calc=deal_income, duty=deal, amount=income)
                deal_r.save()
                remainder = 0
                break
            if deal_income.deal_data.first().income_account.currency.short_name in ['USD', 'USDT']:
                income = deal_income.deal_data.first().income_amount * deal_income.deal_data.first().income_rata
            else:
                income = deal_income.deal_data.first().income_amount
            if income <= expense:
                if income == expense:
                    deal.is_repaid = True
                if deal.amount_repaid:
                    deal.amount_repaid += income
                else:
                    deal.amount_repaid = income
                deal.save()
                deal_income.status_ie = 3
                deal_income.save()
                deal_r = DealRepayment(calc=deal_income, duty=deal, amount=income)
                deal_r.save()
            else:
                if deal.deal_data.first().expense_account.currency.short_name in ['USD', 'USDT']:
                    deal.amount_repaid = deal.deal_data.first().expense_amount * deal.rate
                else:
                    deal.amount_repaid = deal.deal_data.first().expense_amount
                deal.status_ie = 2
                deal.is_repaid = True
                deal.save()
                deal_income.status_ie = 3
                deal_income.save()
                remainder = income - expense
                deal_r = DealRepayment(calc=deal_income, duty=deal, amount=expense)
                deal_r.save()








def make_ie_calculate_full():
    from catalog.models import Contractor
    contractor_id = 1
    with transaction.atomic():
        contractor = Contractor.objects.select_for_update().get(id=contractor_id)

        reset_calculations(contractor)
        apply_opening_duty(contractor)
        apply_ie_statuses(contractor)
        calculate_duty_repaid(contractor)





def recalculate_remainders_v3():
    from catalog.models import Bill
    from operation.models import IncomeExpense, Deal, HistoryBill
    from collections import defaultdict

    HistoryBill.objects.all().delete()
    in_exes = IncomeExpense.objects.filter(deal__closed=True).select_related(
        'income_account', 'expense_account'
    ).order_by('deal__date_create')#('date_create')
    balances = defaultdict(lambda: Decimal('0'))
    for bill in (Bill.objects.all()):
        balances[bill.id] = bill.initial_remainder or Decimal('0')
    to_create = []
    for op in in_exes:
        inc_before = inc_after = Decimal('0')
        exp_before = exp_after = Decimal('0')

        if op.income_account:
            acct_id = op.income_account.id
            inc_before = balances[acct_id]
            inc_after = inc_before + (op.income_amount or Decimal('0'))
            balances[acct_id] = inc_after

            if acct_id == 22:
                print(
                    f"[INCOME][Deal {op.deal_id}] "
                    f"+{op.income_amount} | "
                    f"{inc_before} → {inc_after}"
                )

        if op.expense_account:
            acct_id = op.expense_account.id
            exp_before = balances[acct_id]
            exp_after = exp_before - (op.expense_amount or Decimal('0')) #- (op.commission or Decimal('0'))
            balances[acct_id] = exp_after

            if acct_id == 22:
                print(
                    f"[EXPENSE][Deal {op.deal_id}] "
                    f"-{op.expense_amount} | "
                    f"{exp_before} → {exp_after}"
                )
        to_create.append(HistoryBill(
            in_ex=op,
            income_before=inc_before,
            income_after=inc_after,
            expense_before=exp_before,
            expense_after=exp_after,
        ))
    HistoryBill.objects.bulk_create(to_create)
    return True



def recalculate_remainders_v2():
    from catalog.models import Bill
    from operation.models import IncomeExpense, Deal, HistoryBill
    HistoryBill.objects.all().delete()
    in_exes = IncomeExpense.objects.all()
    for in_ex in in_exes:
        income_before = 0
        income_after = 0
        expense_before = 0
        expense_after = 0
        if in_ex.income_account:
            historys_in = HistoryBill.objects.filter(
                Q(in_ex__income_account=in_ex.income_account) | Q(in_ex__expense_account=in_ex.income_account))
            if historys_in.count() == 0:
                income_before = in_ex.income_account.initial_remainder
                income_after = in_ex.income_account.initial_remainder + in_ex.income_amount
            else:
                historys_in_last = historys_in.last()
                if historys_in_last.income_after and historys_in_last.income_after != Decimal('0'):
                    income_before = historys_in_last.income_after
                    income_after = historys_in_last.income_after + in_ex.income_amount
                if historys_in_last.expense_after and historys_in_last.expense_after != Decimal('0'):
                    income_before = historys_in_last.expense_after
                    income_after = historys_in_last.expense_after + in_ex.income_amount
        if in_ex.expense_account:
            historys_ex = HistoryBill.objects.filter(
                Q(in_ex__income_account=in_ex.expense_account) | Q(in_ex__expense_account=in_ex.expense_account))
            if historys_ex.count() == 0:
                expense_before = in_ex.expense_account.initial_remainder
                expense_after = in_ex.expense_account.initial_remainder - in_ex.expense_amount
            else:
                historys_ex_last = historys_ex.last()
                if historys_ex_last.expense_after and historys_ex_last.expense_after != Decimal('0'):

                    expense_before = historys_ex_last.expense_after
                    expense_after = historys_ex_last.expense_after - in_ex.expense_amount
                if historys_ex_last.income_after and historys_ex_last.income_after != Decimal('0'):

                    expense_before = historys_ex_last.income_after
                    expense_after = historys_ex_last.income_after - in_ex.expense_amount
        if expense_after != 0 or income_after != 0:
            hist_obj = HistoryBill(in_ex=in_ex)
            hist_obj.income_before = income_before
            hist_obj.income_after = income_after
            hist_obj.expense_before = expense_before
            hist_obj.expense_after = expense_after
            hist_obj.save()
    return True

def recalculate_remainders():
    from catalog.models import Bill
    from operation.models import IncomeExpense, Deal, HistoryBill
    HistoryBill.objects.all().delete()
    deals = Deal.objects.all()
    for deal in deals:
        in_exes = IncomeExpense.objects.filter(deal=deal)
        for in_ex in in_exes:
            if in_ex.income_account:
                historys_in = HistoryBill.objects.filter(Q(in_ex__income_account=in_ex.income_account) | Q(in_ex__expense_account=in_ex.income_account)).filter(Q(income_after__isnull=False) & ~Q(income_after=Decimal('0'))|Q(expense_after__isnull=False) & ~Q(expense_after=Decimal('0')))
                if historys_in.count() == 0:
                    income_before = in_ex.income_account.initial_remainder
                    income_after = in_ex.income_account.initial_remainder + in_ex.income_amount
                else:
                    if historys_in.last().income_after and historys_in.last().income_after != 0:
                        income_before = historys_in.last().income_after
                        income_after = historys_in.last().income_after + in_ex.income_amount
                    elif historys_in.last().expense_after and historys_in.last().expense_after != 0:
                        income_before = historys_in.last().expense_after
                        income_after = historys_in.last().expense_after + in_ex.income_amount
            else:
                income_before = 0
                income_after = 0
            if in_ex.expense_account:
                historys_ex = HistoryBill.objects.filter(Q(in_ex__income_account=in_ex.expense_account) | Q(in_ex__expense_account=in_ex.expense_account)).filter(Q(income_after__isnull=False) & ~Q(income_after=Decimal('0'))|Q(expense_after__isnull=False) & ~Q(expense_after=Decimal('0')))
                if historys_ex.count() == 0:

                    expense_before = in_ex.expense_account.initial_remainder
                    expense_after = in_ex.expense_account.initial_remainder - in_ex.expense_amount
                else:
                    if historys_ex.last().expense_after and historys_ex.last().expense_after != 0:

                        expense_before = historys_ex.last().expense_after
                        expense_after = historys_ex.last().expense_after - in_ex.expense_amount
                    elif historys_ex.last().income_after and historys_ex.last().income_after != 0:

                        expense_before = historys_ex.last().income_after
                        expense_after = historys_ex.last().income_after - in_ex.expense_amount

            else:
                expense_before = 0
                expense_after = 0
            if expense_after != 0 or income_after != 0:
                hist_obj = HistoryBill(in_ex=in_ex)
                hist_obj.income_before = income_before
                hist_obj.income_after = income_after
                hist_obj.expense_before = expense_before
                hist_obj.expense_after = expense_after
                hist_obj.save()
    return True

def recalculate_dutys():
    from catalog.models import ContractorHistory, Contractor
    from operation.models import IncomeExpense, Deal, ContractorDebtOperation
    ContractorHistory.objects.all().delete()
    contractors = Contractor.objects.all()
    deals = Deal.objects.filter(closed=True).order_by('date_create')
    for deal in deals:
        if deal.contractor:
            contractor = deal.contractor
            duty = 0
            duty_usdt = 0
            duty_cost = 0
            in_exes = IncomeExpense.objects.filter(deal=deal)
            for in_ex in in_exes:
                if in_ex.income_account and not in_ex.expense_account:
                    if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                        duty += in_ex.income_amount * in_ex.income_rate
                        duty_cost += in_ex.income_amount * in_ex.income_rate
                    else:
                        duty += in_ex.income_amount
                        duty_cost += in_ex.income_amount
                if in_ex.expense_account and not in_ex.income_account:
                    if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                        duty -= in_ex.expense_amount * deal.rate
                        duty_cost -= in_ex.expense_amount * in_ex.expense_rate
                    else:
                        duty -= in_ex.expense_amount
                        duty_cost -= in_ex.expense_amount
            if deal.duty_deal != 0:
                duty -= deal.duty_deal
                duty_cost -= deal.duty_deal
            #if deal.id == deals.first().id:
            if ContractorHistory.objects.filter(contractor=contractor).count() == 0:
                if contractor.duty:
                    duty += contractor.duty
                    duty_cost += contractor.duty
            else:
                last_hist = ContractorHistory.objects.filter(contractor=contractor).last()
                duty += last_hist.duty
                duty_usdt += last_hist.duty_usdt
                duty_cost += last_hist.duty
            history_obj = ContractorHistory(contractor=contractor, deal=deal)
            history_obj.date_create = deal.date_create
            history_obj.duty = Decimal(duty)
            history_obj.duty_usdt = Decimal(duty_usdt)
            history_obj.duty_cost = Decimal(duty_cost)
            history_obj.save()
        else:
            debts = ContractorDebtOperation.objects.filter(deal=deal)
            for debt in debts:
                contractor = debt.contractor
                amount = debt.amount
                currency_name = debt.currency.short_name
                percent = debt.percent
                operation_type = debt.operation_type
                duty = 0
                duty_usdt = 0
                if currency_name == 'USDT':
                    if ContractorHistory.objects.filter(contractor=contractor).count() != 0:
                        last_hist = ContractorHistory.objects.filter(contractor=contractor).last()
                        duty_usdt += last_hist.duty_usdt
                        duty += last_hist.duty
                        if operation_type == 'write_off':
                            duty_usdt -= amount
                        else:
                            duty_usdt += amount
                        history_obj = ContractorHistory(contractor=contractor, deal=deal)
                        history_obj.duty = Decimal(duty)
                        history_obj.duty_usdt = Decimal(duty_usdt)
                        history_obj.save()
                    else:
                        duty += contractor.duty
                        duty_usdt += contractor.duty_usdt
                        if operation_type == 'write_off':
                            duty_usdt -= amount
                        else:
                            duty_usdt += amount
                        history_obj = ContractorHistory(contractor=contractor, deal=deal)
                        history_obj.duty = Decimal(duty)
                        history_obj.duty_usdt = Decimal(duty_usdt)
                        history_obj.save()
                else:
                    if ContractorHistory.objects.filter(contractor=contractor).count() != 0:
                        last_hist = ContractorHistory.objects.filter(contractor=contractor).last()
                        duty_usdt += last_hist.duty_usdt
                        duty += last_hist.duty
                        if operation_type == 'write_off':
                            duty -= amount
                        else:
                            duty += amount
                        history_obj = ContractorHistory(contractor=contractor, deal=deal)
                        history_obj.duty = Decimal(duty)
                        history_obj.duty_usdt = Decimal(duty_usdt)
                        history_obj.save()
                    else:
                        duty += contractor.duty
                        duty_usdt += contractor.duty_usdt
                        if operation_type == 'write_off':
                            duty -= amount
                        else:
                            duty += amount
                        history_obj = ContractorHistory(contractor=contractor, deal=deal)
                        history_obj.duty = Decimal(duty)
                        history_obj.duty_usdt = Decimal(duty_usdt)
                        history_obj.save()



def create_dutys():
    from catalog.models import ContractorHistory, Contractor
    from operation.models import IncomeExpense, Deal
    contractors = Contractor.objects.all()
    for contractor in contractors:
        deals = Deal.objects.filter(contractor=contractor)
        for deal in deals:
            duty = 0
            in_exes = IncomeExpense.objects.filter(deal=deal)
            for in_ex in in_exes:
                if in_ex.income_account and not in_ex.expense_account:
                    if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                        duty -= in_ex.income_amount * in_ex.income_rate
                    else:
                        duty -= in_ex.income_amount
                if in_ex.expense_account and not in_ex.income_account:
                    if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                        duty += in_ex.expense_amount * deal.rate
                    else:
                        duty += in_ex.expense_amount
            if deal.duty_deal != 0:
                duty += deal.duty_deal
            if deal.id == deals.first().id:
                if contractor.duty:
                    duty += contractor.duty
            else:
                last_hist = ContractorHistory.objects.filter(contractor=contractor).last()
                duty += last_hist.duty
            history_obj = ContractorHistory(contractor=contractor, deal=deal)
            history_obj.date_create = deal.date_create
            history_obj.duty = Decimal(duty)
            history_obj.save()




def show_rate(currency):
    from operation.models import IncomeExpense
    from catalog.models import Bill, Currency
    currency_obj = Currency.objects.get(short_name=currency)
    if currency_obj.rate:
        old_rate = currency_obj.rate
    else:
        old_rate = 0
    bills = Bill.objects.filter(currency__short_name=currency)
    bills_sum = bills.aggregate(
        sum=Sum('initial_remainder'),

    )['sum']
    bills_id = Bill.objects.filter(currency__short_name=currency).values_list('id')
    expense_sum = IncomeExpense.objects.filter(expense_account__currency__short_name=currency).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum('expense_amount'),
    )['sum'] or Decimal('0')
    expense_id = IncomeExpense.objects.filter(expense_account__currency__short_name=currency).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).values_list('id')
    initial_rate = bills.first().initial_rate
    deals_sum = IncomeExpense.objects.filter(income_account__currency__short_name=currency).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('income_amount') * F('income_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum'] or Decimal('0')
    deals_id = IncomeExpense.objects.filter(income_account__currency__short_name=currency).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).values_list('id')
    total_income = IncomeExpense.objects.filter(income_account__currency__short_name=currency).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum('income_amount'),
    )['sum'] or Decimal('0')
    total_id = IncomeExpense.objects.filter(income_account__currency__short_name=currency).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).values_list('id')
    total_expense = expense_sum
    total_rate = (((bills_sum - expense_sum) * initial_rate) + deals_sum) / (bills_sum + total_income - total_expense)
    return  old_rate, total_rate, bills_id, expense_id, deals_id, total_id

def update_currency_rate_v3_calculate_test(currency, deal_id):
    from operation.models import IncomeExpense
    from catalog.models import Bill, Currency
    currency_obj = Currency.objects.get(short_name=currency)
    if currency_obj.rate:
        old_rate = currency_obj.rate
    else:
        old_rate = 0
    bills = Bill.objects.filter(currency__short_name=currency, status=True)
    bills_sum = bills.aggregate(
        sum=Sum('initial_remainder'),

    )['sum']
    print('Сумма первоначальных балансов ' + str(bills_sum))
    bills_total = bills.aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('initial_remainder') * F('initial_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum']
    print('Сумма первоначальных балансов * курсы ' + str(bills_total))
    expense_sum = IncomeExpense.objects.filter(expense_account__currency__short_name=currency, deal_id__lte=deal_id, deal__closed=True).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum('expense_amount'),
    )['sum'] or Decimal('0')
    print('Сумма расходов ' + str(expense_sum))
    expense_total = IncomeExpense.objects.filter(expense_account__currency__short_name=currency, deal_id__lte=deal_id, deal__closed=True).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('expense_amount') * F('expense_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum'] or Decimal('0')
    print('Сумма расходов + курсы ' + str(expense_total))
    initial_rate = bills.first().initial_rate
    deals_sum = IncomeExpense.objects.filter(income_account__currency__short_name=currency, deal_id__lte=deal_id, deal__closed=True).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('income_amount') * F('income_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum'] or Decimal('0')
    print('Сумма приходов + курсы ' + str(deals_sum))
    total_income = IncomeExpense.objects.filter(income_account__currency__short_name=currency, deal_id__lte=deal_id, deal__closed=True).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum('income_amount'),
    )['sum'] or Decimal('0')
    print('Сумма приходов ' + str(total_income))
    total_expense = expense_sum
    total_rate = (bills_total + deals_sum - expense_total) / (bills_sum + total_income - expense_sum)

    print('Старый и новый курсы')
    print(str(old_rate), str(total_rate))
    return  old_rate, total_rate

def update_currency_rate_v3_calculate(currency, deal_date):
    from operation.models import IncomeExpense
    from catalog.models import Bill, Currency
    currency_obj = Currency.objects.get(short_name=currency)
    if currency_obj.rate:
        old_rate = currency_obj.rate
    else:
        old_rate = 0
    bills = Bill.objects.filter(currency__short_name=currency, status=True)
    bills_sum = bills.aggregate(
        sum=Sum('initial_remainder'),

    )['sum']
    bills_total = bills.aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('initial_remainder') * F('initial_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum']

    debt_operation_subquery = ContractorDebtOperation.objects.filter(
        deal=OuterRef('deal'),
        currency__short_name=OuterRef('expense_account__currency__short_name'),
        amount=OuterRef('expense_amount')
    )
    add_income_sum = (
        Deal.objects
        .annotate(
            usdt_count=Count(
                'debt_operations',
                filter=Q(
                    debt_operations__currency__short_name='USDT',
                    debt_operations__operation_type='write_off'
                ),
                distinct=True
            ),
            rub_count=Count(
                'debt_operations',
                filter=Q(
                    debt_operations__currency__short_name='RUB',
                    debt_operations__operation_type='write_on'
                ),
                distinct=True
            ),
            usdt_sum=Sum(
                'debt_operations__amount',
                filter=Q(
                    debt_operations__currency__short_name='USDT',
                    debt_operations__operation_type='write_off'
                )
            ),
        )
        .filter(
            usdt_count=1,
            rub_count=1,
            date_create__lte=deal_date,
            closed=True
        )
        .aggregate(
            total_sum=Coalesce(Sum('usdt_sum'), Decimal('0'))
        )
    )['total_sum'] or 0
    add_expense_sum= (
            Deal.objects
            .annotate(
                usdt_count=Count(
                    'debt_operations',
                    filter=Q(
                        debt_operations__currency__short_name='RUB',
                        debt_operations__operation_type='write_off'
                    ),
                    distinct=True
                ),
                rub_count=Count(
                    'debt_operations',
                    filter=Q(
                        debt_operations__currency__short_name='USDT',
                        debt_operations__operation_type='write_on'
                    ),
                    distinct=True
                ),
                usdt_sum=Sum(
                    'debt_operations__amount',
                    filter=Q(
                        debt_operations__currency__short_name='USDT',
                        debt_operations__operation_type='write_on'
                    )
                ),
            )
            .filter(
                usdt_count=1,
                rub_count=1,
                date_create__lte=deal_date,
                closed=True
            )
            .aggregate(
                total_sum=Coalesce(Sum('usdt_sum'), Decimal('0'))
            )
        )['total_sum'] or 0
    expense_sum = IncomeExpense.objects.filter(
        expense_account__currency__short_name=currency,
        deal__date_create__lte=deal_date,
        deal__closed=True
    ).exclude(
        Q(
            expense_amount=F('income_amount'),
            income_account__currency__short_name=F('expense_account__currency__short_name')
        )
    ).annotate(
        has_matching_debt=Exists(debt_operation_subquery)
    ).exclude(
        has_matching_debt=True
    ).aggregate(
        sum=Sum('expense_amount'),
    )['sum'] or Decimal('0')
    expense_sum += add_expense_sum
    add_income_total = (
        Deal.objects
        .annotate(
            usdt_count=Count(
                'debt_operations',
                filter=Q(
                    debt_operations__currency__short_name='USDT',
                    debt_operations__operation_type='write_off'
                ),
                distinct=True
            ),
            rub_count=Count(
                'debt_operations',
                filter=Q(
                    debt_operations__currency__short_name='RUB',
                    debt_operations__operation_type='write_on'
                ),
                distinct=True
            ),
            rub_sum=Sum(
                'debt_operations__amount',
                filter=Q(
                    debt_operations__currency__short_name='RUB',
                    debt_operations__operation_type='write_on'
                )
            ),
        )
        .filter(
            usdt_count=1,
            rub_count=1,
            date_create__lte=deal_date,
            closed=True
        )
        .aggregate(
            total_sum=Coalesce(Sum('rub_sum'), Decimal('0'))
        )
    )['total_sum'] or 0
    add_expense_total = (
                            Deal.objects
                            .annotate(
                                usdt_count=Count(
                                    'debt_operations',
                                    filter=Q(
                                        debt_operations__currency__short_name='RUB',
                                        debt_operations__operation_type='write_off'
                                    ),
                                    distinct=True
                                ),
                                rub_count=Count(
                                    'debt_operations',
                                    filter=Q(
                                        debt_operations__currency__short_name='USDT',
                                        debt_operations__operation_type='write_on'
                                    ),
                                    distinct=True
                                ),
                                course_sum=Sum(
                                    ExpressionWrapper(
                                        F('debt_operations__amount') * F('rate_contractors'),
                                        output_field=DecimalField(max_digits=18, decimal_places=8)
                                    ),
                                    filter=Q(
                                        debt_operations__currency__short_name='USDT',
                                        debt_operations__operation_type='write_on'
                                    )
                                ),
                            )
                            .filter(
                                usdt_count=1,
                                rub_count=1,
                                date_create__lte=deal_date,
                                closed=True
                            )
                            .aggregate(
                                total_sum=Coalesce(Sum('course_sum'), Decimal('0'))
                            )
                        )['total_sum'] or 0
    expense_total = IncomeExpense.objects.filter(
        expense_account__currency__short_name=currency,
        deal__date_create__lte=deal_date,
        deal__closed=True
    ).exclude(
        Q(
            expense_amount=F('income_amount'),
            income_account__currency__short_name=F('expense_account__currency__short_name')
        )
    ).annotate(
        has_matching_debt=Exists(debt_operation_subquery)
    ).exclude(
        has_matching_debt=True
    ).aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('expense_amount') * F('expense_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum'] or Decimal('0')
    expense_total += add_expense_total
    initial_rate = bills.first().initial_rate



    deals_sum = IncomeExpense.objects.filter(
        income_account__currency__short_name=currency,
        deal__date_create__lte=deal_date,
        deal__closed=True
    ).exclude(
        Q(
            expense_amount=F('income_amount'),
            income_account__currency__short_name=F('expense_account__currency__short_name')
        ) |
        Q(
            deal__debt_operations__percent__gt=0
        )
    ).aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('income_amount') * F('income_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum'] or Decimal('0')
    deals_sum += add_income_total

    total_income = IncomeExpense.objects.filter(
        income_account__currency__short_name=currency,
        deal__date_create__lte=deal_date,
        deal__closed=True
    ).exclude(
        Q(
            expense_amount=F('income_amount'),
            income_account__currency__short_name=F('expense_account__currency__short_name')
        ) |
        Q(deal__debt_operations__percent__gt=0)  # <-- исключаем сделки с заполненным percent
    ).distinct().aggregate(
        sum=Sum('income_amount')
    )['sum'] or Decimal('0')
    total_percent = ContractorDebtOperation.objects.filter(
        deal__deal_data__income_account__currency__short_name=currency,
        deal__date_create__lte=deal_date,
        deal__closed=True
    ).aggregate(
        sum=Sum('percent')
    )['sum'] or Decimal('0')
    total_income += add_income_sum
    total_income += total_percent
    total_expense = expense_sum

    total_rate = (bills_total + deals_sum - expense_total) / (bills_sum + total_income - expense_sum)

    currency_obj.rate = total_rate
    currency_obj.save()
    bills.update(rate=total_rate)
    return  old_rate, total_rate


def update_currency_rate_v2_calculate(currency, deal_id):
    from operation.models import IncomeExpense
    from catalog.models import Bill, Currency
    currency_obj = Currency.objects.get(short_name=currency)
    if currency_obj.rate:
        old_rate = currency_obj.rate
    else:
        old_rate = 0
    bills = Bill.objects.filter(currency__short_name=currency)
    bills_sum = bills.aggregate(
        sum=Sum('initial_remainder'),

    )['sum']
    expense_sum = IncomeExpense.objects.filter(expense_account__currency__short_name=currency, deal_id__lte=deal_id).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum('expense_amount'),
    )['sum'] or Decimal('0')
    initial_rate = bills.first().initial_rate
    deals_sum = IncomeExpense.objects.filter(income_account__currency__short_name=currency, deal_id__lte=deal_id).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('income_amount') * F('income_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum'] or Decimal('0')
    total_income = IncomeExpense.objects.filter(income_account__currency__short_name=currency, deal_id__lte=deal_id).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum('income_amount'),
    )['sum'] or Decimal('0')
    total_expense = expense_sum
    total_rate = (((bills_sum - expense_sum) * initial_rate) + deals_sum) / (bills_sum + total_income - total_expense)
    currency_obj.rate = total_rate
    currency_obj.save()
    bills.update(rate=total_rate)
    return  old_rate, total_rate

def update_currency_rate_v3(currency):
    from operation.models import IncomeExpense
    from catalog.models import Bill, Currency
    currency_obj = Currency.objects.get(short_name=currency)
    if currency_obj.rate:
        old_rate = currency_obj.rate
    else:
        old_rate = 0
    bills = Bill.objects.filter(currency__short_name=currency)
    bills_sum = bills.aggregate(
        sum=Sum('initial_remainder'),

    )['sum']
    bills_total = bills.aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('initial_remainder') * F('initial_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum']
    expense_sum = \
    IncomeExpense.objects.filter(expense_account__currency__short_name=currency).exclude(
        Q(expense_amount=F('income_amount'),
          income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum('expense_amount'),
    )['sum'] or Decimal('0')
    expense_total = \
    IncomeExpense.objects.filter(expense_account__currency__short_name=currency).exclude(
        Q(expense_amount=F('income_amount'),
          income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('expense_amount') * F('expense_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum'] or Decimal('0')

    deals_sum = IncomeExpense.objects.filter(
        income_account__currency__short_name=currency
    ).exclude(
        Q(
            expense_amount=F('income_amount'),
            income_account__currency__short_name=F('expense_account__currency__short_name')
        ) |
        Q(deal__debt_operations__percent__gt=0)  # <-- исключаем сделки с заполненным percent
    ).distinct().aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('income_amount') * F('income_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum'] or Decimal('0')
    total_income = IncomeExpense.objects.filter(
        income_account__currency__short_name=currency
    ).exclude(
        Q(
            expense_amount=F('income_amount'),
            income_account__currency__short_name=F('expense_account__currency__short_name')
        ) |
        Q(deal__debt_operations__percent__gt=0)  # <-- исключаем сделки с заполненным percent
    ).distinct().aggregate(
        sum=Sum('income_amount')
    )['sum'] or Decimal('0')
    total_percent = ContractorDebtOperation.objects.filter(
        deal__deal_data__income_account__currency__short_name=currency,
        deal__closed=True
    ).aggregate(
        sum=Sum('percent')
    )['sum'] or Decimal('0')
    total_income += total_percent
    total_expense = expense_sum
    total_rate = (bills_total + deals_sum - expense_total) / (bills_sum + total_income - expense_sum)
    currency_obj.rate = total_rate
    currency_obj.save()
    bills.update(rate=total_rate)
    return old_rate, total_rate

def update_currency_rate_v2(currency):
    from operation.models import IncomeExpense
    from catalog.models import Bill, Currency
    currency_obj = Currency.objects.get(short_name=currency)
    if currency_obj.rate:
        old_rate = currency_obj.rate
    else:
        old_rate = 0
    bills = Bill.objects.filter(currency__short_name=currency)
    bills_sum = bills.aggregate(
        sum=Sum('initial_remainder'),

    )['sum']
    expense_sum = IncomeExpense.objects.filter(expense_account__currency__short_name=currency).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum('expense_amount'),
    )['sum'] or Decimal('0')
    initial_rate = bills.first().initial_rate
    deals_sum = IncomeExpense.objects.filter(income_account__currency__short_name=currency).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum(
            ExpressionWrapper(
                F('income_amount') * F('income_rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )['sum'] or Decimal('0')
    total_income = IncomeExpense.objects.filter(income_account__currency__short_name=currency).exclude(Q(expense_amount=F('income_amount'),income_account__currency__short_name=F('expense_account__currency__short_name'))).aggregate(
        sum=Sum('income_amount'),
    )['sum'] or Decimal('0')
    total_expense = expense_sum
    total_rate = (((bills_sum - expense_sum) * initial_rate) + deals_sum) / (bills_sum + total_income - total_expense)
    currency_obj.rate = total_rate
    currency_obj.save()
    bills.update(rate=total_rate)
    return  old_rate, total_rate

def update_currency_rate(currency):
    from operation.models import IncomeExpense
    from catalog.models import Bill, Currency
    currency_obj = Currency.objects.get(short_name=currency)
    if currency_obj.rate:
        old_rate = currency_obj.rate
    else:
        old_rate = 0
    bills = Bill.objects.filter(currency__short_name=currency)
    total_income_1 = data_1["total_income"] or 0
    weighted_sum_1 = data_1["weighted_sum"] or 0


    data_2 = IncomeExpense.objects.filter(income_account__currency__short_name=currency,
                                          expense_account__currency__short_name__in=['USD', 'USDT']).aggregate(
        total_income=Sum(ExpressionWrapper(F('income_amount') - F('expense_amount'),output_field=DecimalField(max_digits=18, decimal_places=8))),
        weighted_sum=Sum(
            ExpressionWrapper(
                F('income_amount') * ((F('expense_amount') * F('expense_account__rate'))/F('income_amount')) - F('expense_amount') * F('expense_account__rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )

    total_income_2 = data_2["total_income"] or 0
    weighted_sum_2 = data_2["weighted_sum"] or 0

    data_3 = IncomeExpense.objects.filter(income_account__currency__short_name=currency,
                                          expense_account__currency__short_name__in=['RUB']).aggregate(
        total_income=Sum('income_amount'),
        weighted_sum=Sum(
            ExpressionWrapper(
                F('expense_amount') * F('expense_account__rate'),
                output_field=DecimalField(max_digits=18, decimal_places=8)
            )
        )
    )
    total_income_3 = data_3["total_income"] or 0
    weighted_sum_3 = data_3["weighted_sum"] or 0

    total_rate = (weighted_sum_1 + weighted_sum_2 + weighted_sum_3) / (total_income_1 + total_income_2 + total_income_3)
    #total_rate = (weighted_sum_1 + weighted_sum_3 - weighted_sum_2) / (total_income_1 + total_income_3 - total_income_2)
    currency_obj.rate = total_rate
    currency_obj.save()
    bills.update(rate=total_rate)
    return old_rate, total_rate



def get_total_rate_balance(account, type_bill, expense_account=None):
    from operation.models import IncomeExpense
    if type_bill == 'income_expense_v3':
        old_bill_remainder = account.initial_remainder
        data_income = IncomeExpense.objects.filter(income_account=account).aggregate(
            total=Sum('income_amount'),
        )
        data_expense = IncomeExpense.objects.filter(expense_account=account).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('expense_amount') ,#+ F('commission')
                    output_field=DecimalField(max_digits=10, decimal_places=3)
                )
            )
        )
        total_income = data_income['total'] or 0
        total_expense = data_expense['total'] or 0
        total_sum = old_bill_remainder + (total_income - total_expense)
        return total_sum
    if type_bill == 'income_expense_v2':
        old_bill_rate = account.initial_rate
        old_bill_remainder = account.initial_remainder
        data = IncomeExpense.objects.filter(income_account=account, deal__closed=True)
        if data.count() != 0 and account.currency.short_name in ['USD', 'USDT']:
            data_1 = data.filter(expense_account__currency__short_name__in=['USD', 'USDT']).aggregate(
                total_income=Sum('income_amount'),
                weighted_sum=Sum(
                    ExpressionWrapper(
                        F('expense_amount') * F('expense_account__rate'),
                        output_field=DecimalField(max_digits=10, decimal_places=3)
                    )
                )
            )
            total_income_1 = data_1["total_income"] or 0
            weighted_sum_1 = data_1["weighted_sum"] or 0

            data_2 = data.filter(expense_account__currency__short_name__in=['RUB']).aggregate(
                total_income=Sum('income_amount'),
                weighted_sum=Sum('expense_amount'),
            )
            total_income_2 = data_2["total_income"] or 0
            weighted_sum_2 = data_2["weighted_sum"] or 0

            total_rate = ((old_bill_remainder * old_bill_rate) + weighted_sum_1 + weighted_sum_2) / (old_bill_remainder + total_income_1 + total_income_2)
        else:
            total_rate = old_bill_rate
        data_income = IncomeExpense.objects.filter(income_account=account).aggregate(
            total=Sum('income_amount'),
        )
        data_expense = IncomeExpense.objects.filter(expense_account=account).aggregate(
            total=Sum(
                    ExpressionWrapper(
                        F('expense_amount') ,#+ F('commission')
                        output_field=DecimalField(max_digits=10, decimal_places=3)
                    )
                )
        )
        total_income = data_income['total'] or 0
        total_expense = data_expense['total'] or 0
        total_sum = old_bill_remainder + (total_income - total_expense)
        return total_sum, total_rate
    if type_bill == 'income_expense':
        old_bill_rate = account.initial_rate
        old_bill_remainder = account.initial_remainder
        data_1 = IncomeExpense.objects.filter(deal__category__name='Внутренний закуп', income_account=account).aggregate(
            total_income=Sum('income_amount'),
            weighted_sum=Sum(
                ExpressionWrapper(
                    F('income_amount') * F('deal__rate'),
                    output_field=DecimalField(max_digits=10, decimal_places=3)
                )
            )
        )
        total_income_1 = data_1["total_income"] or 0
        weighted_sum_1 = data_1["weighted_sum"] or 0
        weighted_avg_rate_1 = weighted_sum_1 / total_income_1 if total_income_1 > 0 else 0

        data_2 = IncomeExpense.objects.filter(deal__category__name='Перевод между своими счетами',
                                              income_account=account).aggregate(
            total_income=Sum('income_amount'),
            weighted_sum=Sum(
                ExpressionWrapper(
                    F('income_amount') * F('expense_account__rate'),
                    output_field=DecimalField(max_digits=10, decimal_places=3)
                )
            )
        )
        total_income_2 = data_2["total_income"] or 0
        weighted_sum_2 = data_2["weighted_sum"] or 0
        weighted_avg_rate_2 = weighted_sum_2 / total_income_2 if total_income_2 > 0 else 0

        data_3 = IncomeExpense.objects.filter(income_account=account, income_account__currency__short_name='USDT', expense_account__currency__short_name='USDT').aggregate(
            total_income=Sum('income_amount'),
            weighted_sum=Sum(
                ExpressionWrapper(
                    F('expense_amount') * F('expense_account__rate'),
                    output_field=DecimalField(max_digits=10, decimal_places=3)
                )
            )
        )
        total_income_3 = data_3["total_income"] or 0
        weighted_sum_3 = data_3["weighted_sum"] or 0
        weighted_avg_rate_3 = weighted_sum_3 / total_income_3 if total_income_3 > 0 else 0

        data_4 = IncomeExpense.objects.filter(income_account=account, income_account__currency__short_name='USD', expense_account__currency__short_name='USDT').aggregate(
            total_income=Sum('income_amount'),
            weighted_sum=Sum(
                ExpressionWrapper(
                    F('income_amount') * F('rate_spare'),
                    output_field=DecimalField(max_digits=10, decimal_places=3)
                )
            )
        )
        total_income_4 = data_4["total_income"] or 0
        weighted_sum_4 = data_4["weighted_sum"] or 0
        weighted_avg_rate_4 = weighted_sum_4 / total_income_4 if total_income_4 > 0 else 0

        total_income_new = total_income_1 + total_income_2 + total_income_3 + total_income_4
        weighted_sum_new = weighted_sum_1 + weighted_sum_2 + weighted_sum_3 + weighted_sum_4

        total_remainder = old_bill_remainder + weighted_sum_new
        if total_remainder != 0:
            total_rate = (old_bill_remainder * old_bill_rate + total_income_new) / total_remainder
        else:
            total_rate = (old_bill_remainder * old_bill_rate) / old_bill_remainder

        data_income = IncomeExpense.objects.filter(income_account=account).aggregate(
            total=Sum('income_amount'),
        )
        data_expense = IncomeExpense.objects.filter(expense_account=account).aggregate(
            total=Sum('expense_amount'),
        )
        total_income = data_income['total'] or 0
        total_expense = data_expense['total'] or 0
        total_sum = old_bill_remainder + (total_income - total_expense)
        return total_sum, total_rate
    elif type_bill == 'usd_usdt':
        old_bill_rate = account.initial_rate
        old_bill_remainder = account.initial_remainder
        data = IncomeExpense.objects.filter(income_account=account, expense_account=expense_account).aggregate(
            total_income=Sum('income_amount'),
            weighted_sum=Sum(
                ExpressionWrapper(
                    F('income_amount') * F('rate_spare'),
                    output_field=DecimalField(max_digits=10, decimal_places=3)
                )
            )
        )
        total_income = data["total_income"] or 0
        weighted_sum = data["weighted_sum"] or 0
        weighted_avg_rate = weighted_sum / total_income if total_income > 0 else 0
        total_rate = ((old_bill_remainder * old_bill_rate) + (total_income * weighted_avg_rate)) / (old_bill_remainder + total_income)
        data_income = IncomeExpense.objects.filter(income_account=account).aggregate(
            total=Sum('income_amount'),
        )
        data_expense = IncomeExpense.objects.filter(expense_account=account).aggregate(
            total=Sum('expense_amount'),
        )
        total_income = data_income['total'] or 0
        total_expense = data_expense['total'] or 0
        total_sum = old_bill_remainder + (total_income - total_expense)
        #total_sum = data["total_income"] + old_bill_remainder
        return total_sum, total_rate
    elif type_bill == 'expense':
        old_bill_rate = account.initial_rate
        old_bill_remainder = account.initial_remainder
        data_income = IncomeExpense.objects.filter(income_account=account).aggregate(
            total=Sum('income_amount'),
        )
        data_expense = IncomeExpense.objects.filter(expense_account=account).aggregate(
            total=Sum('expense_amount'),
        )
        total_sum = old_bill_remainder + (data_income['total'] - data_expense['total'])
        return total_sum



def get_weighted_avg_rate(deal):
    from operation.models import IncomeExpense
    old_bill_rate = deal.old_bill_rate
    old_bill_remainder = deal.old_bill_remainder
    data = IncomeExpense.objects.filter(deal=deal).aggregate(
        total_income=Sum('income_amount'),
        weighted_sum=Sum(
            ExpressionWrapper(
                F('income_amount') * F('income_account__rate'),
                output_field=DecimalField(max_digits=10, decimal_places=3)
            )
        )
    )
    total_income = data["total_income"] or 0
    weighted_sum = data["weighted_sum"] or 0

    weighted_avg_rate = weighted_sum / total_income if total_income > 0 else 0
    total_rate = ((old_bill_remainder * old_bill_rate) + (total_income * weighted_avg_rate)) / (old_bill_remainder + total_income)
    return total_rate

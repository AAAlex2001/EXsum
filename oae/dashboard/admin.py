from django.contrib import admin, messages
from .models import *
from unfold.admin import ModelAdmin
from unfold.views import UnfoldModelAdminViewMixin
from django.views.generic import TemplateView
from django.urls import path
from .utils import  *
from django.template.response import TemplateResponse
from unfold.sites import UnfoldAdminSite
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
import json
from .forms import DateRangeForm, TypeForm
from catalog.models import Contractor, Category, ContractorHistory
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.utils.safestring import mark_safe
from django.conf import settings
from datetime import datetime, time, timezone as dt_timezone
from django.utils import timezone
from django.shortcuts import get_object_or_404
from collections import OrderedDict
from operation.models import *
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Q




class CustomPageView(UnfoldModelAdminViewMixin, TemplateView):
    title = "Графики"
    permission_required = ()
    template_name = "graphics.html"

@admin.register(Histogram)
class HistogramAdmin(ModelAdmin):
    change_list_template = "graphics.html"

    class Media:
        css = {
            'all': (
                'dashboard/custom_dash.css',
            )
        }
        js = ('dashboard/custom_dash.js',)

    def get_list_display(self, request):
        if request.user.groups.filter(name='restricted').exists():
            return []
        return super().get_list_display(request)

    def has_view_permission(self, request, obj=None):
        if request.user.groups.filter(name='restricted').exists():
            return False
        return super().has_view_permission(request, obj=obj)

    def has_change_permission(self, request, obj=None):
        if request.user.groups.filter(name='restricted').exists():
            return False
        return super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(name='restricted').exists():
            return False
        return super().has_delete_permission(request, obj=obj)

    def changelist_view(self, request, extra_context=None):
        x, y = get_count_deals()
        data = {
            "labels": x,
            "values": y,
        }
        extra_context = extra_context or {}
        extra_context["chart_data"] = data
        extra_context["charts"] = []
        x, y = get_marginality()
        extra_context["charts"].append({'type': 'line', 'name': 'Средняя маржинальности', 'x': x, 'y': y})
        x, y = get_dds()
        extra_context["charts"].append({'type': 'bar', 'name': 'Список ДДС', 'x': x, 'y': y})
        x, y = get_total_profit_by_week()
        extra_context["charts"].append({'type': 'line', 'name': 'Общая прибыль', 'x': x, 'y': y})
        x, y = get_total_profit_by_year()
        extra_context["charts"].append({'type': 'line', 'name': 'Прибыль по месяцам', 'x': x, 'y': y})
        x, y = get_count_deals()
        extra_context["charts"].append({'type': 'bar', 'name': 'Количество сделок', 'x': x, 'y': y})
        return super().changelist_view(request, extra_context=extra_context)



def fifo_opening_detail(request):
    contractor = Contractor.objects.get(id=1)
    repayments = DealRepayment.objects.filter(
        Q(contractor_duty=True) |
        Q(calc__debt_operations__contractor=contractor,
          calc__debt_operations__operation_type='write_on',
          calc__debt_operations__currency__short_name='RUB'),
        #calc__contractor=contractor
    ).select_related('calc').distinct().order_by('date_create')

    columns = ['Приход/Сделка', 'Сумма погашения']
    rows = []

    for r in repayments:
        calc_url = f'/admin/operation/deal/{r.calc.id}/change/'
        rows.append([
            mark_safe(
                f'<a href="{calc_url}">'
                f'Приход {r.calc.id} {r.date_create.strftime("%d.%m.%Y")}'
                f'</a>'
            ),
            r.amount
        ])

    ctx = admin.site.each_context(request)
    ctx.update({
        'title': 'Погашения начального долга',
        'columns': columns,
        'rows': rows,
        'selected': 'fifo'
    })
    return TemplateResponse(request, 'analytics_fifo_detail.html', ctx)

def fifo_deal_detail(request, deal_id):
    deal = get_object_or_404(Deal, id=deal_id)
    repayments = deal.repayments.select_related('calc').order_by('date_create')

    columns = ['Приход/Сделка', 'Сумма погашения']
    rows = []

    for r in repayments:
        calc_url = f'/admin/operation/deal/{r.calc.id}/change/'
        rows.append([
            mark_safe(
                f'<a href="{calc_url}">'
                f'Приход {r.calc.id} {r.date_create.strftime("%d.%m.%Y")}'
                f'</a>'
            ),
            r.amount
        ])

    ctx = admin.site.each_context(request)
    ctx.update({
        'title': f'Погашения по сделке {deal.id}',
        'columns': columns,
        'rows': rows,
        'selected': 'fifo'
    })
    return TemplateResponse(request, 'analytics_fifo_detail.html', ctx)


def analytics_view(request):
    if request.user.groups.filter(name='restricted').exists():
        return HttpResponseForbidden("Доступ запрещён")
    view_type = request.GET.get('type', 'days')
    columns, rows = [], []
    chart_label = 'Доход'
    if view_type == 'days':
        #columns = ['Дата', 'Доход общий', 'Моя метрика']
        columns = ['Дата', 'Доход общий', 'Моя метрика USD', 'Комиссия', 'Моя метрика USDT', 'Никита', 'Доход ИП']
        rows    = get_revenue('days')
        rows_for_chart = [(d, float(val)) for d, val in get_revenue_chart('days')]
    elif view_type == 'months':
        total_rows = get_revenue('months')  # [(month, total_net), ...]
        cont_map, contractors = get_revenue_months_by_contractor_values_only()
        month_dict = {row[0]: row for row in total_rows}
        # Создаем словарь по месяцам, чтобы добавить текущий месяц


        # Сортируем месяцы
        all_months_sorted = sorted(month_dict.keys(), key=lambda d: datetime.strptime(d, '%m.%Y'))

        # Формируем итоговые строки

        rows = []
        for month in all_months_sorted:
            base_row = month_dict.get(month)

            if not base_row:
                base_row = [
                    month,
                    Decimal('0.000'),
                    Decimal('0.000'),
                    Decimal('0.000'),
                    Decimal('0.000'),
                    Decimal('0.000'),
                    Decimal('0.000'),
                ]

            month_date = datetime.strptime(month, '%m.%Y').date()


            month_contractors = cont_map.get(month_date, {})

            contractors_row = [
                month_contractors.get(contractor, Decimal('0.000'))
                for contractor in contractors
            ]

            rows.append((*base_row, *contractors_row))

        columns = ['Дата', 'Доход общий', 'Моя метрика USD', 'Комиссия', 'Моя метрика USDT', 'Никита',
                   'Доход ИП'] + contractors
        rows_for_chart = [(d, float(total)) for d, total, *rest in rows]
    elif view_type == 'dds':
        chart_label = 'Остаток'
        columns = get_dds_columns()#['ДДС', 'Приход', 'Расход']
        rows = get_dds_table()
        table = get_dds_table()
        columns = get_dds_columns()
        months = columns[1:]
        remainder_row = table[-1][1:]
        rows_for_chart =  [
            (month, float(value))
            for month, value in zip(months, remainder_row)
        ]
    elif view_type == 'fifo':
        columns = ['Тип долга', 'Комментарий', 'Сумма долга', 'Сумма в нац.', 'Статус бар',
                   'Прибыль заложенная', 'Прибыль фактическая', 'Дата полного рассчета', 'Период рассчета',
                   'Погашено', 'Приход']  # /Сделка', 'Сумма погашения']
        rows = []

        contractor = Contractor.objects.get(id=1)

        # --- начальный долг ---
        opening_repayments = DealRepayment.objects.filter(
            contractor_duty=True,
            #calc__contractor=contractor
        ).select_related('calc').order_by('date_create')
        opening_repaid = opening_repayments.aggregate(s=Sum('amount'))['s'] or 0
        percent = (opening_repaid / abs(contractor.duty)) * 100 if opening_repaid else 0
        total_amount = DealRepayment.objects.aggregate(
            total=Sum('amount')
        )['total'] or 0
        total_amount = Decimal(total_amount).quantize(
            Decimal('0.001'),
            rounding=ROUND_HALF_UP
        )
        contractor_duty = contractor.duty.quantize(
            Decimal('0.001'),
            rounding=ROUND_HALF_UP
        )
        detail_url = '/admin/analytics-view/fifo/opening/'
        rows.append(['Начальный долг', '', 0, abs(contractor_duty), str(int(percent)) + ' %',
                     0, 0, str(opening_repayments.last().date_create.strftime('%d.%m.%Y')), 0,
                     total_amount, mark_safe(f'<a href="{detail_url}" class="text-blue-600 underline">Посмотреть</a>')])


        # --- расходные сделки ---
        # обычные расходные сделки
        expense_deals_normal = Deal.objects.filter(
            contractor=contractor,
            deal_data__income_account__isnull=True,
            closed=True  # new
        )

        # сделки только с duty_deal
        duty_only_deals = Deal.objects.filter(
            contractor=contractor,
            deal_data__isnull=True,
            duty_deal__isnull=False,
            closed=True  # new
        )

        all_expense_deals = list({d.id: d for d in list(expense_deals_normal) + list(duty_only_deals)}.values())
        all_expense_deals.sort(key=lambda d: d.date_create)

        for deal in all_expense_deals:
            repayments = deal.repayments.select_related('calc').order_by('date_create')
            repaid = repayments.aggregate(s=Sum('amount'))['s'] or 0

            # определяем сумму долга
            if deal.deal_data.exists():
                deal_expense = deal.deal_data.first()
                if deal_expense.expense_account.currency.short_name in ['USD', 'USDT']:
                    expense_amount = deal_expense.expense_amount * deal.rate
                    expense_sum = deal_expense.expense_amount
                    profit = deal_expense.expense_amount * deal.rate - deal_expense.expense_amount * deal_expense.expense_rate
                else:
                    expense_amount = deal_expense.expense_amount
                    expense_sum = 0
                    profit = 0
            elif hasattr(deal, 'duty_deal') and deal.duty_deal is not None:
                expense_amount = deal.duty_deal  # берём сумму в национальной валюте
                expense_sum = 0
                profit = 0
            else:
                expense_amount = 0
                expense_sum = 0
                profit = 0
            opening_repaid = repayments.aggregate(s=Sum('amount'))['s'] or 0
            percent = (opening_repaid / expense_amount) * 100 if opening_repaid else 0
            deal_url = f'/admin/operation/deal/{deal.id}/change/'
            if profit != 0 and percent != 0:
                profit_fact = (Decimal(profit) * (percent / Decimal(100)))
            else:
                profit_fact = 0
            if repayments.count() != 0:
                date_last_repay = repayments.last().date_create.strftime('%d.%m.%Y')
                all_days = (repayments.last().date_create - deal.date_create).days
            else:
                date_last_repay = '-'
                all_days = 0

            expense_amount = expense_amount.quantize(
                Decimal('0.001'),
                rounding=ROUND_HALF_UP
            )
            if expense_sum != 0:
                expense_sum = expense_sum.quantize(
                    Decimal('0.001'),
                    rounding=ROUND_HALF_UP
                )
            if profit != 0:
                profit = profit.quantize(
                    Decimal('0.001'),
                    rounding=ROUND_HALF_UP
                )
            if profit_fact != 0:
                profit_fact = profit_fact.quantize(
                    Decimal('0.001'),
                    rounding=ROUND_HALF_UP
                )
            if repaid != 0:
                repaid = repaid.quantize(
                    Decimal('0.001'),
                    rounding=ROUND_HALF_UP
                )
            detail_url = f'/admin/analytics-view/fifo/deal/{deal.id}/'
            rows.append([mark_safe(
                f'<a href="{deal_url}">Сделка расхода {deal.date_create.strftime("%d.%m.%Y")} {deal.id}</a>'),
                         deal.comment, expense_sum, expense_amount, str(int(percent)) + ' %', profit,
                         profit_fact, date_last_repay,
                         all_days,
                         repaid, mark_safe(f'<a href="{detail_url}" class="text-blue-600 underline">Посмотреть</a>')])


        rows_for_chart = []  # можно сделать график по суммам погашений, если нужно
        chart_label = 'Погашения'

    elif view_type == 'metrics':
        columns = ['Период','CostDebt', 'AprCost']
        rows = []
        contractor = Contractor.objects.get(id=1)
        now = timezone.now()
        now_date = timezone.now().date()
        days = 14
        start_date = now - timedelta(days=days)
        end_date = now
        values_14 = get_ip_income('days', start_date, end_date)
        total_14_profit = sum(values_14.values())
        history_qs = (
            ContractorHistory.objects
            .filter(
                contractor=contractor,
                date_create__date__lte=now_date
            )
            .order_by('date_create')
        )
        daily_duty = OrderedDict()
        last_value = Decimal('0')
        for i in range(days):
            day = now - timedelta(days=i)

            day_history = (
                history_qs
                .filter(date_create__date__lte=day)
                .last()
            )

            if day_history and day_history.duty_cost is not None:
                last_value = day_history.duty_cost

            daily_duty[day] = last_value
        total_14 = sum(daily_duty.values(), Decimal('0')) / Decimal(days)
        apr_cost = (total_14_profit / Decimal(total_14)) * Decimal((365 / 14))
        rows.append(['14', total_14.quantize(Decimal('0.001'),rounding=ROUND_HALF_UP), apr_cost.quantize(Decimal('0.001'),rounding=ROUND_HALF_UP)])
        days = 30
        start_date = now - timedelta(days=days)
        end_date = now
        values_30 = get_ip_income('days', start_date, end_date)
        total_30_profit = sum(values_30.values())
        daily_duty = OrderedDict()
        last_value = Decimal('0')
        for i in range(days):
            day = now - timedelta(days=i)

            day_history = (
                history_qs
                .filter(date_create__date__lte=day)
                .last()
            )

            if day_history and day_history.duty_cost is not None:
                last_value = day_history.duty_cost

            daily_duty[day] = last_value
        total_30 = sum(daily_duty.values(), Decimal('0')) / Decimal(days)

        apr_cost = (total_30_profit / Decimal(total_30)) * Decimal((365 / 30))
        rows.append(['30',total_30.quantize(Decimal('0.001'),rounding=ROUND_HALF_UP), apr_cost.quantize(Decimal('0.001'),rounding=ROUND_HALF_UP)])


        days = 90
        start_date = now - timedelta(days=days)
        end_date = now
        values_90 = get_ip_income('days', start_date, end_date)
        total_90_profit = sum(values_90.values())
        daily_duty = OrderedDict()
        last_value = Decimal('0')
        for i in range(days):
            day = now - timedelta(days=i)

            day_history = (
                history_qs
                .filter(date_create__date__lte=day)
                .last()
            )

            if day_history and day_history.duty_cost is not None:
                last_value = day_history.duty_cost

            daily_duty[day] = last_value
        total_90 = sum(daily_duty.values(), Decimal('0')) / Decimal(days)

        apr_cost = (total_90_profit / Decimal(total_90)) * Decimal((365 / 90))
        rows.append(['90', total_90.quantize(Decimal('0.001'),rounding=ROUND_HALF_UP), apr_cost.quantize(Decimal('0.001'),rounding=ROUND_HALF_UP)])


        days = 180
        start_date = now - timedelta(days=days)
        end_date = now
        values_180 = get_ip_income('days', start_date, end_date)
        total_180_profit = sum(values_180.values())
        daily_duty = OrderedDict()
        last_value = Decimal('0')
        for i in range(days):
            day = now - timedelta(days=i)

            day_history = (
                history_qs
                .filter(date_create__date__lte=day)
                .last()
            )

            if day_history and day_history.duty_cost is not None:
                last_value = day_history.duty_cost

            daily_duty[day] = last_value
        total_180 = sum(daily_duty.values(), Decimal('0')) / Decimal(days)

        apr_cost = (total_180_profit / Decimal(total_180)) * Decimal((365 / 180))
        rows.append(['180', total_180.quantize(Decimal('0.001'),rounding=ROUND_HALF_UP), apr_cost.quantize(Decimal('0.001'),rounding=ROUND_HALF_UP)])

        days = 365
        start_date = now - timedelta(days=days)
        end_date = now
        values_365 = get_ip_income('days', start_date, end_date)
        total_365_profit = sum(values_365.values())
        daily_duty = OrderedDict()
        last_value = Decimal('0')
        for i in range(days):
            day = now - timedelta(days=i)

            day_history = (
                history_qs
                .filter(date_create__date__lte=day)
                .last()
            )

            if day_history and day_history.duty_cost is not None:
                last_value = day_history.duty_cost

            daily_duty[day] = last_value
        total_365 = sum(daily_duty.values(), Decimal('0')) / Decimal(days)

        apr_cost = (total_365_profit / Decimal(total_365)) * Decimal((365 / 365))
        rows.append(['365', total_365.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
                     apr_cost.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)])
        rows_for_chart = []  # можно сделать график по суммам погашений, если нужно
        chart_label = 'Метрика'
    ctx = admin.site.each_context(request)
    ctx.update({
        'title':    'Аналитика',
        'columns':  columns,
        'rows':     rows,
        'rows_for_chart_json': json.dumps(rows_for_chart),
        'selected': view_type,
        'chart_label': chart_label,
        'highlight_words': ["Приходы", "Расходы"]
    })
    return TemplateResponse(request, 'analytics.html', ctx)

def report_view(request):
    from operation.models import IncomeExpense, Deal, ContractorDebtOperation


    form = DateRangeForm(request.GET or None)
    type_form = TypeForm(request.GET or None)
    data = []
    date_from = date_to = None
    total_data = {'total_income': 0, 'total_expense': 0, 'total_rate': 0}
    bill_name = 'Не выбран'
    if form.is_valid() and type_form.is_valid():
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        if date_from and date_to:
            if date_from.date() == date_to.date():
                date_from = datetime.combine(date_from.date(), time.min)
                date_to = datetime.combine(date_to.date(), time.max)
        selected_type = type_form.cleaned_data.get('type')
        bill_type = type_form.cleaned_data.get('bill_type')
        data = []
        common_data = {}
        bill_name = ''
        if bill_type == 'uae':
            bill_name = 'USDT ОАЭ'
            if selected_type == 'aggregates':
                deals = Deal.objects.filter(date_create__gte=date_from, date_create__lte=date_to, closed=True, category__id__in=[2])#category__id__in=[2],
                incomes = []
                expenses = []
                for deal in deals:
                    income = 0
                    if IncomeExpense.objects.filter(deal=deal, expense_account__name='USDT ОАЭ').count() != 0:
                        in_ex = IncomeExpense.objects.filter(deal=deal, expense_account__name='USDT ОАЭ').first()
                        deal_id = deal.id
                        date_str = deal.date_create.strftime('%Y-%m-%d %H:%M')
                        type = 'Агрегаты'

                        if deal.national_currency and deal.national_currency != 0:
                            income += deal.national_currency
                        else:
                            if in_ex.income_account:
                                if in_ex.income_account.currency.short_name == 'RUB':
                                    income += in_ex.income_amount
                            else:
                                if ContractorDebtOperation.objects.filter(deal=deal).count() != 0:
                                    debt = ContractorDebtOperation.objects.filter(deal=deal).first()
                                    if debt.currency.short_name not in ['USD', 'USDT']:
                                        income += debt.amount
                        expense = in_ex.expense_amount
                        expenses.append(expense)
                        incomes.append(income)
                        rate = income / expense
                        rate = '{0} '.format(str(rate.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                        link_url = settings.SITE_URL + 'admin/operation/deal/' + str(deal_id) + '/change/'
                        deal_link =  mark_safe(f'<a href="{link_url}">{deal_id}</a>')
                        if deal.deal_1c:
                            deal_1c = deal.deal_1c
                        else:
                            deal_1c = '-'
                        data.append({'id': deal_link, 'date': date_str, 'type': type,  'income': income, 'expense': expense, 'rate': rate, 'deal_1c': deal_1c})
                try:
                    total_sum = sum(incomes)/sum(expenses)
                except:
                    total_sum = 0
                total_income = '{0} '.format(str(Decimal(sum(incomes)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                total_expense = '{0} '.format(str(Decimal(sum(expenses)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                total_rate = '{0} '.format(str(Decimal(total_sum).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                total_data = {'total_income': total_income, 'total_expense': total_expense, 'total_rate': total_rate}
            elif selected_type == 'delivery':
                deals = Deal.objects.filter(Q(contractor_id=1) | Q(debt_operations__contractor_id=1), date_create__gte=date_from, date_create__lte=date_to, closed=True).exclude(cashflow__id=22)#category__id__in=[4]
                incomes = []
                expenses = []

                for deal in deals:
                    income = 0
                    expense = 0
                    if IncomeExpense.objects.filter(deal=deal).count() != 0:
                        in_ex = IncomeExpense.objects.filter(deal=deal).first()
                        deal_id = deal.id
                        date_str = deal.date_create.strftime('%Y-%m-%d %H:%M')
                        type = 'Доставка'
                        if deal.national_currency:
                            income = deal.national_currency
                            incomes.append(income)
                        else:
                            if in_ex.income_account:
                                if in_ex.income_account.currency.short_name == 'RUB':
                                    income = in_ex.income_amount
                                    incomes.append(income)
                                else:
                                    continue
                            else:
                                continue
                        expense = in_ex.expense_amount
                        if expense == 0:
                            expense = int(0)
                        expenses.append(expense)
                        link_url = settings.SITE_URL + 'admin/operation/deal/' + str(deal_id) + '/change/'
                        deal_link =  mark_safe(f'<a href="{link_url}">{deal_id}</a>')
                        if deal.deal_1c:
                            deal_1c = deal.deal_1c
                        else:
                            deal_1c = '-'
                        data.append(
                            {'id': deal_link, 'date': date_str, 'type': type, 'income': income, 'expense': expense, 'rate': '', 'deal_1c': deal_1c})
                    elif ContractorDebtOperation.objects.filter(deal=deal).count() != 0:
                        if ContractorDebtOperation.objects.filter(deal=deal).count() >= 2 and ContractorDebtOperation.objects.filter(deal=deal, contractor__id=1, operation_type='write_on').count() != 0:
                            in_ex = IncomeExpense.objects.filter(deal=deal).first()
                            deal_id = deal.id
                            date_str = deal.date_create.strftime('%Y-%m-%d %H:%M')
                            type = 'Доставка'
                            #if ContractorDebtOperation.objects.filter(deal=deal, contractor__id=1, operation_type='write_off').count() != 0:
                            ip_income = ContractorDebtOperation.objects.filter(deal=deal, contractor__id=1, operation_type='write_on').first()
                            if ip_income.currency:
                                if ip_income.currency.short_name in ['USD', 'USDT']:
                                    income  = deal.national_currency
                                    incomes.append(income)
                                else:
                                    income = ip_income.amount
                                    incomes.append(income)
                            expense = 0
                            exp_contrs = ContractorDebtOperation.objects.filter(deal=deal, contractor__id=1, operation_type='write_on')
                            if expense == 0:
                                expense = int(0)
                            expenses.append(expense)
                            link_url = settings.SITE_URL + 'admin/operation/deal/' + str(deal_id) + '/change/'
                            deal_link = mark_safe(f'<a href="{link_url}">{deal_id}</a>')
                            if deal.deal_1c:
                                deal_1c = deal.deal_1c
                            else:
                                deal_1c = '-'
                            data.append(
                                {'id': deal_link, 'date': date_str, 'type': type, 'income': income, 'expense': expense,
                                 'rate': '', 'deal_1c': deal_1c})
                total_income = '{0} '.format(str(Decimal(sum(incomes)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                total_expense = 0
                total_rate = 0
                total_data = {'total_income': total_income, 'total_expense': total_expense, 'total_rate': total_rate}
        elif bill_type == 'kor':
            bill_name = 'КОРЕЯ USDT'
            if selected_type == 'aggregates':
                deals = Deal.objects.filter(date_create__gte=date_from, date_create__lte=date_to,
                                            closed=True, category__id__in=[2])  # category__id__in=[2],
                incomes = []
                expenses = []
                for deal in deals:
                    income = 0
                    if IncomeExpense.objects.filter(deal=deal, expense_account__name='USDT КОРЕЯ').count() != 0:
                        in_ex = IncomeExpense.objects.filter(deal=deal, expense_account__name='USDT КОРЕЯ').first()
                        deal_id = deal.id
                        date_str = deal.date_create.strftime('%Y-%m-%d %H:%M')
                        type = 'Агрегаты'

                        if deal.national_currency and deal.national_currency != 0:
                            income += deal.national_currency
                            # incomes.append(income)
                        else:
                            if in_ex.income_account:
                                if in_ex.income_account.currency.short_name == 'RUB':
                                    income += in_ex.income_amount
                                    # incomes.append(income)
                            else:
                                if ContractorDebtOperation.objects.filter(deal=deal).count() != 0:
                                    debt = ContractorDebtOperation.objects.filter(deal=deal).first()
                                    if debt.currency.short_name not in ['USD', 'USDT']:
                                        income += debt.amount
                        expense = in_ex.expense_amount
                        expenses.append(expense)
                        incomes.append(income)
                        rate = income / expense
                        rate = '{0} '.format(str(rate.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                        link_url = settings.SITE_URL + 'admin/operation/deal/' + str(deal_id) + '/change/'
                        deal_link = mark_safe(f'<a href="{link_url}">{deal_id}</a>')
                        if deal.deal_1c:
                            deal_1c = deal.deal_1c
                        else:
                            deal_1c = '-'
                        data.append(
                            {'id': deal_link, 'date': date_str, 'type': type, 'income': income, 'expense': expense,
                             'rate': rate, 'deal_1c': deal_1c})
                try:
                    total_sum = sum(incomes) / sum(expenses)
                except:
                    total_sum = 0
                total_income = '{0} '.format(
                    str(Decimal(sum(incomes)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                total_expense = '{0} '.format(
                    str(Decimal(sum(expenses)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                total_rate = '{0} '.format(str(Decimal(total_sum).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                total_data = {'total_income': total_income, 'total_expense': total_expense, 'total_rate': total_rate}
            elif selected_type == 'delivery':
                deals = Deal.objects.filter(Q(contractor_id=1) | Q(debt_operations__contractor_id=1),
                                            date_create__gte=date_from, date_create__lte=date_to, closed=True, cashflow__name='ДОСТАВКА КОРЕЯ').exclude(
                    cashflow__id=22)  # category__id__in=[4]
                incomes = []
                expenses = []

                for deal in deals:
                    income = 0
                    expense = 0
                    if IncomeExpense.objects.filter(deal=deal).count() != 0:
                        in_ex = IncomeExpense.objects.filter(deal=deal).first()
                        deal_id = deal.id
                        date_str = deal.date_create.strftime('%Y-%m-%d %H:%M')
                        type = 'Доставка'
                        if deal.national_currency:
                            income = deal.national_currency
                            incomes.append(income)
                        else:
                            if in_ex.income_account:
                                if in_ex.income_account.currency.short_name == 'RUB':
                                    income = in_ex.income_amount
                                    incomes.append(income)
                                else:
                                    continue
                            else:
                                continue
                        expense = in_ex.expense_amount
                        if expense == 0:
                            expense = int(0)
                        expenses.append(expense)
                        link_url = settings.SITE_URL + 'admin/operation/deal/' + str(deal_id) + '/change/'
                        deal_link = mark_safe(f'<a href="{link_url}">{deal_id}</a>')
                        if deal.deal_1c:
                            deal_1c = deal.deal_1c
                        else:
                            deal_1c = '-'
                        data.append(
                            {'id': deal_link, 'date': date_str, 'type': type, 'income': income, 'expense': expense,
                             'rate': '', 'deal_1c': deal_1c})
                    elif ContractorDebtOperation.objects.filter(deal=deal).count() != 0:
                        if ContractorDebtOperation.objects.filter(
                                deal=deal).count() >= 2 and ContractorDebtOperation.objects.filter(deal=deal,
                                                                                                   contractor__id=1,
                                                                                                   operation_type='write_on').count() != 0:
                            in_ex = IncomeExpense.objects.filter(deal=deal).first()
                            deal_id = deal.id
                            date_str = deal.date_create.strftime('%Y-%m-%d %H:%M')
                            type = 'Доставка'
                            # if ContractorDebtOperation.objects.filter(deal=deal, contractor__id=1, operation_type='write_off').count() != 0:
                            ip_income = ContractorDebtOperation.objects.filter(deal=deal, contractor__id=1,
                                                                               operation_type='write_on').first()
                            if ip_income.currency:
                                if ip_income.currency.short_name in ['USD', 'USDT']:
                                    income = deal.national_currency
                                    incomes.append(income)
                                else:
                                    income = ip_income.amount
                                    incomes.append(income)
                            expense = 0
                            exp_contrs = ContractorDebtOperation.objects.filter(deal=deal, contractor__id=1,
                                                                                operation_type='write_on')
                            if expense == 0:
                                expense = int(0)
                            expenses.append(expense)
                            link_url = settings.SITE_URL + 'admin/operation/deal/' + str(deal_id) + '/change/'
                            deal_link = mark_safe(f'<a href="{link_url}">{deal_id}</a>')
                            if deal.deal_1c:
                                deal_1c = deal.deal_1c
                            else:
                                deal_1c = '-'
                            data.append(
                                {'id': deal_link, 'date': date_str, 'type': type, 'income': income, 'expense': expense,
                                 'rate': '', 'deal_1c': deal_1c})
                total_income = '{0} '.format(
                    str(Decimal(sum(incomes)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
                total_expense = 0
                total_rate = 0
                total_data = {'total_income': total_income, 'total_expense': total_expense, 'total_rate': total_rate}
        elif bill_type == 'installment':
            deals = Deal.objects.filter(contractor__id=1, date_create__gte=date_from, date_create__lte=date_to,
                                        closed=True, cashflow__id=23)  # category__id__in=[4]
            incomes = []
            expenses = []
            for deal in deals:
                if IncomeExpense.objects.filter(deal=deal).count() != 0:
                    in_ex = IncomeExpense.objects.filter(deal=deal).first()
                    deal_id = deal.id
                    date_str = deal.date_create.strftime('%Y-%m-%d %H:%M')
                    type = 'Доставка'
                    if deal.national_currency:
                        income = deal.national_currency
                        incomes.append(income)
                    else:
                        if in_ex.income_account:
                            if in_ex.income_account.currency.short_name == 'RUB':
                                income = in_ex.income_amount
                                incomes.append(income)
                            else:
                                continue
                        else:
                            continue
                    expense = in_ex.expense_amount
                    if expense == 0:
                        expense = int(0)
                    expenses.append(expense)
                    link_url = settings.SITE_URL + 'admin/operation/deal/' + str(deal_id) + '/change/'
                    deal_link = mark_safe(f'<a href="{link_url}">{deal_id}</a>')
                    if deal.deal_1c:
                        deal_1c = deal.deal_1c
                    else:
                        deal_1c = '-'
                    data.append(
                        {'id': deal_link, 'date': date_str, 'type': type, 'income': income, 'expense': expense,
                         'rate': '', 'deal_1c': deal_1c})
            total_income = '{0} '.format(str(Decimal(sum(incomes)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
            total_expense = 0
            total_rate = 0
            total_data = {'total_income': total_income, 'total_expense': total_expense, 'total_rate': total_rate}
        elif bill_type == 'installment_20':
            deals = Deal.objects.filter(contractor__id=1, date_create__gte=date_from, date_create__lte=date_to,
                                        closed=True, cashflow__id=24)  # category__id__in=[4]
            incomes = []
            expenses = []
            for deal in deals:
                if IncomeExpense.objects.filter(deal=deal).count() != 0:
                    in_ex = IncomeExpense.objects.filter(deal=deal).first()
                    deal_id = deal.id
                    date_str = deal.date_create.strftime('%Y-%m-%d %H:%M')
                    type = 'Доставка'
                    if deal.national_currency:
                        income = deal.national_currency
                        incomes.append(income)
                    else:
                        if in_ex.income_account:
                            if in_ex.income_account.currency.short_name == 'RUB':
                                income = in_ex.income_amount
                                incomes.append(income)
                            else:
                                continue
                        else:
                            continue
                    expense = in_ex.expense_amount
                    if expense == 0:
                        expense = int(0)
                    expenses.append(expense)
                    link_url = settings.SITE_URL + 'admin/operation/deal/' + str(deal_id) + '/change/'
                    deal_link = mark_safe(f'<a href="{link_url}">{deal_id}</a>')
                    if deal.deal_1c:
                        deal_1c = deal.deal_1c
                    else:
                        deal_1c = '-'
                    data.append(
                        {'id': deal_link, 'date': date_str, 'type': type, 'income': income, 'expense': expense,
                         'rate': '', 'deal_1c': deal_1c})
            total_income = '{0} '.format(str(Decimal(sum(incomes)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
            total_expense = 0
            total_rate = 0
            total_data = {'total_income': total_income, 'total_expense': total_expense, 'total_rate': total_rate}

    ctx = admin.site.each_context(request)
    ctx.update({
        'title': 'Отчёт по операциям',
        'form': form,
        'data': data,
        'form_type': type_form,
        'total_data': total_data,
        'date_from': date_from,
        'date_to': date_to,
        'bill_name': bill_name
        #'columns': ['ID', 'Дата', 'Сумма'],  # или динамически
    })

    return TemplateResponse(request, 'report.html', ctx)


def analytics_view_dev(request):
    if request.user.groups.filter(name='restricted').exists():
        return HttpResponseForbidden("Доступ запрещён")
    ctx = admin.site.each_context(request)
    ctx.update({
        'title': 'Аналитика',
    })
    return TemplateResponse(request, 'analytics_dev.html', ctx)

def analytics_view_dds(request):
    if request.user.groups.filter(name='restricted').exists():
        return HttpResponseForbidden("Доступ запрещён")
    columns = ['ДДС', 'Приход', 'Расход']
    ctx = admin.site.each_context(request)
    ctx.update({
        'title': 'Аналитика ДДС',
    })
    return TemplateResponse(request, 'analytics_dds.html', ctx)

_original_get_urls = admin.site.get_urls

def get_urls_with_analytics():
    urls = _original_get_urls()
    custom = [
        path(
            'analytics-view/',
            admin.site.admin_view(analytics_view),
            name='analytics_view'
        ),
        path(
            'report_view/',
            admin.site.admin_view(report_view),
            name='report_view'
        ),
        path(
            'analytics-view-dev/',
            admin.site.admin_view(analytics_view_dev),
            name='analytics_view_dev'
        ),
        path(
            'analytics-view-dds/',
            admin.site.admin_view(analytics_view_dds),
            name='analytics_view_dds'
        ),
        # 🔽 НАЧАЛЬНЫЙ ДОЛГ
        path(
            'analytics-view/fifo/opening/',
            admin.site.admin_view(fifo_opening_detail),
            name='fifo_opening_detail'
        ),

        # 🔽 РАСХОДНАЯ СДЕЛКА
        path(
            'analytics-view/fifo/deal/<int:deal_id>/',
            admin.site.admin_view(fifo_deal_detail),
            name='fifo_deal_detail'
        ),
    ]
    return custom + urls

admin.site.get_urls = get_urls_with_analytics
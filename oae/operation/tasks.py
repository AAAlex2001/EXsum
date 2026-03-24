import asyncio
from celery import shared_task
from decimal import Decimal
import time


def normalize_amount(quant: str, decimals: int) -> Decimal:
    return Decimal(quant) / (Decimal(10) ** decimals)

@shared_task
def check_usdts():
    import requests
    from datetime import datetime, date
    from .models import Deal, IncomeExpense
    from catalog.models import Bill
    bill = Bill.objects.get(id=9)
    ADDRESS = 'TUKCdz3fFnVx2tjfaq51hoLYaCYxud9RSS'  
    API_KEY = 'a73df831-6527-4d57-ad28-9e0ae24097bd'        
    url = 'https://apilist.tronscanapi.com/api/token_trc20/transfers'
    params = {
        'toAddress': ADDRESS,
        'limit': 50,
        'start': 0,
        'sort': '-timestamp'
    }

    headers = {
        'TRON-PRO-API-KEY': API_KEY,
        'User-Agent': 'Mozilla/5.0'
    }
    response = requests.get(url, params=params, headers=headers)
    data = response.json()['token_transfers']
    for obj in data:
        if obj['confirmed'] == True:
            today = date.today()
            date_int = obj['block_ts']
            timestamp_s = date_int / 1000
            dt = datetime.fromtimestamp(timestamp_s)
            amount = normalize_amount(obj['quant'], obj['tokenInfo']['tokenDecimal'])
            transaction_id = obj['transaction_id']
            if dt.date() == today:
                try:
                    in_ex = IncomeExpense.objects.get(income_account=bill, transaction_id=transaction_id, date_upload=dt)
                except:
                    deal = Deal()
                    deal.save()
                    in_ex = IncomeExpense(transaction_id=obj['transaction_id'])
                    in_ex.income_account = bill
                    in_ex.deal = deal
                    in_ex.income_amount = amount
                    in_ex.date_upload = dt.date()
                    in_ex.save()
                    bill.remainder += amount
                    bill.save()
                time.sleep(1)
    return True

@shared_task
def downloads_usdts():
    import requests
    from datetime import datetime
    from .models import Deal, IncomeExpense
    ADDRESS = 'TUKCdz3fFnVx2tjfaq51hoLYaCYxud9RSS'  
    API_KEY = 'a73df831-6527-4d57-ad28-9e0ae24097bd'        
    url = 'https://apilist.tronscanapi.com/api/token_trc20/transfers'
    params = {
        'toAddress': ADDRESS,
        'limit': 50,
        'start': 0,
        'sort': '-timestamp'
    }

    headers = {
        'TRON-PRO-API-KEY': API_KEY,
        'User-Agent': 'Mozilla/5.0'
    }
    response = requests.get(url, params=params, headers=headers)
    data = response.json()['token_transfers']
    empty_list = []
    for obj in data:
        amount = normalize_amount(obj['quant'], obj['tokenInfo']['tokenDecimal'])
        try:
            in_ex = IncomeExpense.objects.get(income_account__id=9, income_amount=amount)
            in_ex.transaction_id = obj['transaction_id']
            in_ex.save()
        except:
            empty_list.append(obj)
    return empty_list


@shared_task
def test():
    return 'All work'

@shared_task
def recalculate_courses_dutys_500():
    from .models import Deal, IncomeExpense, LogOperation, CourseBill, HistoryBill, PercentCourse
    from catalog.models import Bill, Currency, Contractor, ContractorHistory
    from catalog.utils import reset_bills_to_initial
    from .utils import recalculate_dutys, get_total_rate_balance, update_currency_rate_v3_calculate
    deals = Deal.objects.filter(closed=True).order_by('date_create')[:500]#all()
    for deal in deals:
        income_expenses = IncomeExpense.objects.filter(deal=deal)
        for in_ex in income_expenses:
            if in_ex.expense_amount and in_ex.expense_account and in_ex.income_amount:
                income_rate = (in_ex.expense_amount * in_ex.expense_account.rate) / in_ex.income_amount
                IncomeExpense.objects.filter(id=in_ex.id).update(income_rate=income_rate)
            if in_ex.expense_account:
                expense_rate = in_ex.expense_account.rate
                IncomeExpense.objects.filter(id=in_ex.id).update(expense_rate=expense_rate)
        ids = set(list(income_expenses.values_list('income_account__id', flat=True)) + list(
            income_expenses.values_list('expense_account__id', flat=True)))
        accounts = Bill.objects.filter(id__in=ids)
        if income_expenses.filter(income_account__currency__short_name__in=['USD', 'USDT']).count() != 0:
            if income_expenses.filter(income_account__currency__short_name='USD').count() != 0:
                old_rate, currency_rate = update_currency_rate_v3_calculate('USD', deal.id)
                try:
                    c_b = CourseBill.objects.get(deal=deal)
                except:
                    c_b = CourseBill(deal=deal)
                if IncomeExpense.objects.filter(income_account__currency__short_name='USD').count() > 1 and IncomeExpense.objects.filter(income_account__currency__short_name='USD').first() != IncomeExpense.objects.filter(income_account__currency__short_name='USD', deal=deal).first():
                    c_b.rate_old = old_rate
                c_b.rate_new = currency_rate
                c_b.save()
            elif income_expenses.filter(income_account__currency__short_name='USDT').count() != 0:
                old_rate, currency_rate = update_currency_rate_v3_calculate('USDT', deal.id)
                try:
                    c_b = CourseBill.objects.get(deal=deal)
                except:
                    c_b = CourseBill(deal=deal)
                if IncomeExpense.objects.filter(income_account__currency__short_name='USDT').count() > 1 and IncomeExpense.objects.filter(income_account__currency__short_name='USDT').first() != IncomeExpense.objects.filter(income_account__currency__short_name='USDT', deal=deal).first():
                    c_b.rate_old = old_rate
                c_b.rate_new = currency_rate
                c_b.save()
    recalculate_dutys()
    return True

@shared_task
def recalculate_courses_dutys():
    from .models import Deal, IncomeExpense, LogOperation, CourseBill, HistoryBill, PercentCourse, ContractorDebtOperation
    from catalog.models import Bill, Currency, Contractor, ContractorHistory
    from catalog.utils import reset_bills_to_initial
    from .utils import recalculate_dutys, get_total_rate_balance, update_currency_rate_v3_calculate, make_ie_calculate_full_v3, update_currency_rate_v3, recalculate_remainders_v3
    import requests
    from django.conf import settings

    TELEGRAM_API = f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/sendMessage"

    def send_telegram_message(chat_id: int, text: str):
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(TELEGRAM_API, data=data, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"Ошибка при отправке сообщения {chat_id}: {e}")


    #send_telegram_message(461670529, "Перерассчет начат")
    CourseBill.objects.all().delete()
    bills = Bill.objects.all()
    reset_bills_to_initial(bills)
    #send_telegram_message(461670529, "Перерассчитываю курсы внутри сделок сделок,остатки счетов и курсы средневзвешенные")
    deals = Deal.objects.filter(closed=True).order_by('date_create')#all()
    for deal in deals:
        income_expenses = IncomeExpense.objects.filter(deal=deal)
        for in_ex in income_expenses:
            if in_ex.expense_amount and in_ex.expense_account and in_ex.income_amount:
                income_rate = (in_ex.expense_amount * in_ex.expense_account.rate) / in_ex.income_amount
                IncomeExpense.objects.filter(id=in_ex.id).update(income_rate=income_rate)
            if in_ex.expense_account:
                expense_rate = in_ex.expense_account.rate
                IncomeExpense.objects.filter(id=in_ex.id).update(expense_rate=expense_rate)
        ids = set(list(income_expenses.values_list('income_account__id', flat=True)) + list(
            income_expenses.values_list('expense_account__id', flat=True)))
        accounts = Bill.objects.filter(id__in=ids)
        for bill in accounts:
            total_sum = get_total_rate_balance(bill, 'income_expense_v3')
            bill.remainder = total_sum
            bill.save()
        if income_expenses.filter(income_account__currency__short_name__in=['USD', 'USDT']).count() != 0:
            if income_expenses.filter(income_account__currency__short_name='USD').count() != 0:
                old_rate, currency_rate = update_currency_rate_v3_calculate('USD', deal.date_create)#update_currency_rate_v3('USD')#
                try:
                    c_b = CourseBill.objects.get(deal=deal)
                except:
                    c_b = CourseBill(deal=deal)
                if IncomeExpense.objects.filter(income_account__currency__short_name='USD').count() > 1 and IncomeExpense.objects.filter(income_account__currency__short_name='USD').first() != IncomeExpense.objects.filter(income_account__currency__short_name='USD', deal=deal).first():
                    c_b.rate_old = old_rate
                c_b.rate_new = currency_rate
                c_b.save()
                #messages.success(request, "Currency {0} rate {1}".format("USD", str(currency_rate)))
            elif income_expenses.filter(income_account__currency__short_name='USDT').count() != 0:
                old_rate, currency_rate = update_currency_rate_v3_calculate('USDT', deal.date_create)#update_currency_rate_v3('USDT')#
                try:
                    c_b = CourseBill.objects.get(deal=deal)
                except:
                    c_b = CourseBill(deal=deal)
                if IncomeExpense.objects.filter(income_account__currency__short_name='USDT').count() > 1 and IncomeExpense.objects.filter(income_account__currency__short_name='USDT').first() != IncomeExpense.objects.filter(income_account__currency__short_name='USDT', deal=deal).first():
                    c_b.rate_old = old_rate
                c_b.rate_new = currency_rate
                c_b.save()
        debts = ContractorDebtOperation.objects.filter(deal=deal)
        nation_debs = debts.filter(operation_type='write_off', currency__short_name='RUB')
        usdt_debs = debts.filter(operation_type='write_on', currency__short_name='USDT')
        if nation_debs.count() != 0 and usdt_debs.count() != 0:
            Deal.objects.filter(id=deal.id).update(rate_contractors=Currency.objects.get(short_name='USDT').rate)
    #send_telegram_message(461670529, "Перерассчитываю историю балансов")
    recalculate_remainders_v3()
    #send_telegram_message(461670529,"Перерассчитываю долги")
    recalculate_dutys()
    #send_telegram_message(461670529, "Перерассчитываю фифо")
    make_ie_calculate_full_v3()
    #send_telegram_message(461670529, "Перерассчет закончен")
    return True
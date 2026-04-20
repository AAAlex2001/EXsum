from django.db import models
from catalog.models import Bill, Currency, CashFlow, Category, Contractor
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.core.exceptions import ValidationError
import reversion
from django.utils import timezone
from django.utils.html import format_html




#@reversion.register(follow=['deal_data'])
class Deal(models.Model):
    class STATUS:
        DEFAULT = 0
        DUTY = 1
        REPAID = 2
        OPENING_DUTY = 3
        TYPES = (
            (DEFAULT, 'Не ип'),
            (DUTY, 'Долг'),
            (REPAID, 'Рассчет'),
            (OPENING_DUTY, 'Начальный долг'),
        )
    carvet_id = models.BigIntegerField('Id внешний', unique=True, db_index=True, blank=True, null=True)
    date_create = models.DateTimeField('Дата создания', blank=True, null=True, default=timezone.now)#auto_now_add=True)
    date_update = models.DateTimeField('Дата обновления', blank=True, null=True, auto_now=True)
    rate = models.DecimalField('Курс',max_digits=10, decimal_places=8,default=0.00, blank=True, null=True)
    rate_contractors = models.DecimalField('Курс момента', max_digits=10, decimal_places=8, default=0.00, blank=True, null=True)
    old_bill_rate = models.DecimalField('Старый курс',max_digits=10, decimal_places=8,default=0.00, blank=True, null=True)
    old_bill_remainder = models.DecimalField('Старый остаток',max_digits=10, decimal_places=8,default=0.00)
    category = models.ForeignKey(Category, verbose_name='Категория', on_delete=models.SET_NULL, related_name='bills_category',blank=True, null=True)
    cashflow = models.ForeignKey(CashFlow, verbose_name='ДДС', on_delete=models.SET_NULL, related_name='bills_cashflow', blank=True, null=True)
    contractor = models.ForeignKey(Contractor, verbose_name='Контрагент', on_delete=models.SET_NULL, related_name='bills_contractor', blank=True, null=True)
    calculated = models.BooleanField('Рассчитано', default=False)
    closed = models.BooleanField('Закончена', default=False)
    comment = models.CharField('Комментарий', max_length=2056, null=True, blank=True)
    duty_deal = models.DecimalField('Долг', max_digits=18, decimal_places=8, default=0.00, blank=True)
    national_currency = models.DecimalField('Нац.валюта', max_digits=18, decimal_places=8, default=0.00)
    deal_1c = models.CharField('Заказ 1с', max_length=1024, null=True, blank=True)
    by_nikita = models.BooleanField('Никита', default=False)

    by_ie = models.BooleanField('ИП', default=False)
    amount_repaid = models.DecimalField('Погашено', max_digits=18, decimal_places=8, default=0.00, null=True, blank=True)
    is_repaid = models.BooleanField('Погашено полностью', default=False)
    #deal_by_duty = models.ForeignKey('self', verbose_name='Сделка долга', on_delete=models.CASCADE, related_name='deal_duty_data',
                             #blank=True, null=True)
    status_ie = models.IntegerField(verbose_name='Статус рассчета', default=STATUS.DEFAULT, choices=STATUS.TYPES)

    class Meta:
        db_table = 'operation_deals'
        ordering = ['id']
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'

    def __str__(self):
        return str(self.id)


    def debts(self):
        operations = self.debt_operations.all()

        if not operations.exists():
            return "-"

        rows = []

        for op in operations:
            amount = op.amount.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            symbol_type = ''
            if op.operation_type == 'write_off':
                symbol_type = '-'
            else:
                symbol_type = '+'
            row = (
                f"{symbol_type}" f"{amount}"
            )
            rows.append(row)

        return format_html("<br>".join(rows))

    def debts_name(self):
        operations = self.debt_operations.all()

        if not operations.exists():
            return "-"

        rows = []

        for op in operations:
            row = (
                f"{op.contractor.name} {op.currency.short_name}"
            )
            rows.append(row)

        return format_html("<br>".join(rows))

    def revenue(self):
        if self.closed:
            if self.category and self.category.id in [2,4]:
                try:
                    total_revenue = 0
                    total_income = 0
                    total_expense = 0
                    in_exes = IncomeExpense.objects.filter(deal=self)
                    debts = ContractorDebtOperation.objects.filter(deal=self)
                    if debts.count() == 0:
                        for in_ex in in_exes:
                            if in_ex.income_account and in_ex.expense_account:
                                if in_ex.income_account.currency.short_name == 'RUB' and in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                                    total_income += in_ex.income_amount
                                    if not in_ex.commission:
                                        total_expense += in_ex.expense_amount * in_ex.expense_rate
                                    else:
                                        total_expense += in_ex.expense_amount * in_ex.expense_rate + in_ex.commission * in_ex.expense_rate
                            if in_ex.expense_account and not in_ex.income_account:
                                if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                                    total_income += (in_ex.expense_amount * self.rate) - (in_ex.expense_amount * in_ex.expense_rate) - in_ex.commission

                    else:
                        #course = self.rate_contractors

                        for in_ex in in_exes:
                            if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                                total_expense += in_ex.expense_amount * in_ex.expense_rate
                        for debt in debts:
                            if debt.currency.short_name == 'RUB' and debt.operation_type == 'write_off':
                                total_income += debt.amount


                    total_revenue = total_income - total_expense

                    if debts.count() == 1 and in_exes.count() == 1:
                        debt = debts.first()
                        if debt.currency.short_name in ['USD', 'USDT'] and debt.operation_type == 'write_off':
                            total_revenue = 0
                    if debts.filter(currency__short_name__in=['USD', 'USDT'],operation_type='write_off').exists() and debts.filter(currency__short_name='RUB',operation_type='write_on').exists() and in_exes.count() == 0:
                        total_revenue = 0
                    if debts.filter(currency__short_name='RUB').count() == 2:
                        if debts.first().amount == debts.last().amount:
                            total_revenue = 0






                    if total_revenue != 0:
                        return total_revenue.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
                    else:
                        for debt in debts:
                            if debt.currency.short_name == 'RUB' and debt.operation_type == 'write_off':
                                total_income += debt.amount
                            if debt.currency.short_name == 'USDT' and debt.operation_type == 'write_on':
                                total_expense += debt.amount * self.rate_contractors#Currency.objects.get(short_name='USDT').rate
                            total_revenue = total_income - total_expense
                        if debts.count() == 1 and in_exes.count() == 1:
                            debt = debts.first()
                            if debt.currency.short_name in ['USD', 'USDT'] and debt.operation_type == 'write_off':
                                total_revenue = 0
                        if debts.filter(currency__short_name__in=['USD', 'USDT'],
                                        operation_type='write_off').exists() and debts.filter(
                                currency__short_name='RUB',
                                operation_type='write_on').exists() and in_exes.count() == 0:
                            total_revenue = 0
                        if debts.filter(currency__short_name='RUB').count() == 2:
                            if debts.first().amount == debts.last().amount:
                                total_revenue = 0
                        if total_revenue != 0:
                            return total_revenue.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
                except:
                    return  '-'
            else:
                total_revenue = 0
                total_income = 0
                total_expense = 0
                debts = ContractorDebtOperation.objects.filter(deal=self)
                for debt in debts:
                    if debt.currency.short_name == 'RUB' and debt.operation_type == 'write_off':
                        total_income += debt.amount
                    if debt.currency.short_name == 'USDT' and debt.operation_type == 'write_on':
                        total_expense += debt.amount * self.rate_contractors#Currency.objects.get(short_name='USDT').rate
                total_revenue = total_income - total_expense
                if debts.filter(currency__short_name='RUB').count() == 2:
                    if debts.first().amount == debts.last().amount:
                        total_revenue = 0
                if total_revenue > 0:
                    return Decimal(total_revenue).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
                else:
                    return '-'
        else:
            return  'Не рассчитана'

    def percent(self):
        if self.closed:
            if self.category and  self.category.id in [2,4]:
                revenue = self.revenue()
                total_percent = 0
                total_income = 0
                in_exes = IncomeExpense.objects.filter(deal=self)
                debts = ContractorDebtOperation.objects.filter(deal=self)
                if debts.count() == 0:
                    for in_ex in in_exes:
                        if in_ex.income_account:
                            if in_ex.income_account.currency.short_name in ['RUB']:
                                total_income += in_ex.income_amount
                            #else:
                                #total_income += in_ex.income_amount * in_ex.income_rate
                else:
                    for debt in debts:
                        if debt.currency.short_name == 'RUB' and debt.operation_type == 'write_off':
                            total_income += debt.amount
                try:
                    total_percent =  revenue / (total_income / 100)
                    return '{0} %'.format(str(Decimal(total_percent).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))
                except:
                    return '-'
            else:
                revenue = self.revenue()
                total_percent = 0
                total_income = 0
                debts = ContractorDebtOperation.objects.filter(deal=self)
                for debt in debts:
                    if debt.currency.short_name == 'RUB' and debt.operation_type == 'write_off':
                        total_income += debt.amount
                try:
                    total_percent = revenue / (total_income / 100)
                    return '{0} %'.format(str(total_percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))
                except Exception as e:
                    return '-'
        else:
            return  'Не рассчитана'

    def duty(self):
        total_duty = 0
        if self.contractor and self.category and self.category.id == 4 and self.closed:
            in_exes = IncomeExpense.objects.filter(deal=self)
            for in_ex in in_exes:
                duty = 0
                if in_ex.income_account and not in_ex.expense_account:
                    if in_ex.income_account.currency.short_name in ['USD', 'USDT']:
                        duty -= in_ex.income_amount * in_ex.income_rate
                    else:
                        duty -= in_ex.income_amount
                if in_ex.expense_account and not in_ex.income_account:
                    if in_ex.expense_account.currency.short_name in ['USD', 'USDT']:
                        #duty += in_ex.expense_amount * in_ex.expense_rate
                        duty += in_ex.expense_amount * self.rate
                    else:
                        duty += in_ex.expense_amount
                if self.duty_deal != 0:
                    duty += self.duty_deal
                total_duty += duty
        if self.contractor:
            duty_contractor = self.contractor.duty
            total_duty = duty_contractor + total_duty
        if total_duty != 0:
            try:
                return  '{0} '.format(str(total_duty.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
            except:
                return total_duty
        return  '-'




    def rate_old(self):
        course_bills = CourseBill.objects.filter(deal=self)
        if course_bills.count() != 0:
            rate = course_bills.first().rate_old
            return '{0} '.format(str(rate.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
        return '-'

    def rate_new(self):
        course_bills = CourseBill.objects.filter(deal=self)
        if course_bills.count() != 0:
            rate = course_bills.first().rate_new
            return '{0} '.format(str(rate.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)))
        return '-'


    revenue.short_description = "Доход"
    percent.short_description = 'Процент'
    rate_old.short_description = "Курс до"
    rate_new.short_description = 'Курс после'
    duty.short_description = 'Долг'
    debts.short_description = 'Тип операции'
    debts_name.short_description = 'Данные операции'


class DealRepayment(models.Model):
    contractor_duty = models.BooleanField('По долгу контрагента', default=False)
    duty = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        related_name='repayments',
        verbose_name='Долг',
        null=True,
        blank=True)
    calc = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        related_name='applied_duties',
        verbose_name='Расчёт'
    )
    amount = models.DecimalField(
        'Сумма погашения',
        max_digits=18,
        decimal_places=8
    )
    date_create = models.DateTimeField()

    class Meta:
        unique_together = ('duty', 'calc')

	

#@reversion.register()
class IncomeExpense(models.Model):
    income_amount = models.DecimalField('Сумма прихода',max_digits=18, decimal_places=8,default=0.00)
    income_account = models.ForeignKey(Bill, verbose_name='Счет прихода', on_delete=models.SET_NULL, related_name='deals_income',blank=True, null=True)
    income_rate = models.DecimalField('Курс прихода', max_digits=18, decimal_places=8,default=0.00, null=True, blank=True)
    expense_amount = models.DecimalField('Сумма расхода', max_digits=18, decimal_places=8,default=0.00, null=True, blank=True)
    expense_account = models.ForeignKey(Bill, verbose_name='Счет расхода', on_delete=models.SET_NULL, related_name='deals_expense',blank=True, null=True)
    expense_rate = models.DecimalField('Курс расхода', max_digits=18, decimal_places=8, default=0.00, null=True,blank=True)
    deal = models.ForeignKey(Deal, verbose_name='Сделка', on_delete=models.CASCADE, related_name='deal_data',blank=True, null=True)
    calculated = models.BooleanField('Рассчитано', default=False)
    date_create = models.DateTimeField('Дата создания', blank=True, null=True, auto_now_add=True)
    date_update = models.DateTimeField(('Дата обновления'), blank=True, null=True, auto_now=True)
    commission = models.DecimalField('Комиссия', max_digits=18, decimal_places=8, default=0.00)
    rate_calculated = models.BooleanField('Рассчитан приход', default=False)
    transaction_id = models.CharField('Hash', max_length=2056, null=True, blank=True)
    date_upload = models.DateField(auto_now_add=True, blank=True, null=True)
    rate_conversion = models.DecimalField('Курс конвертации',max_digits=10, decimal_places=8,default=0.00, blank=True, null=True)



    class Meta:
        db_table = 'operation_deal_in_ex'
        ordering = ['id']
        verbose_name = 'Приход/Расход'
        verbose_name_plural = 'Приходы/Расходы'

    def __str__(self):
        return str(self.id)

    

class ContractorDebtOperation(models.Model):
    OPERATION_TYPE = [
        ('write_off', 'Списание -'),
        ('write_on', 'Зачисление +'),
    ]
    deal = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        related_name='debt_operations'
    )

    contractor = models.ForeignKey(
        Contractor,
        verbose_name='Контрагент',
        on_delete=models.CASCADE,
        related_name='debt_operations'
    )


    operation_type = models.CharField(
        'Тип операции',
        max_length=20,
        choices=OPERATION_TYPE,
        default='write_off',
    )

    amount = models.DecimalField(
        'Сумма операции',
        max_digits=18,
        decimal_places=8
    )

    percent = models.DecimalField(
        'Процент',
        max_digits=10,
        decimal_places=4,
        default=0,
        blank=True
    )

    currency = models.ForeignKey(
        Currency,
        verbose_name='Валюта',
        on_delete=models.SET_NULL,
        null=True
    )


    comment = models.CharField('Комментарий', max_length=512, blank=True, null=True)

    date_create = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'operation_contractor_debt'
        ordering = ['id']
        verbose_name = 'Движения контрагентов'
        verbose_name_plural = 'Движения контрагентов'

    def __str__(self):
        return str(self.id)




class CourseBill(models.Model):
    rate_old = models.DecimalField('Курс до',max_digits=18, decimal_places=8, default=0.00, blank=True, null=True)
    rate_new = models.DecimalField('Курс после',max_digits=18, decimal_places=8,default=0.00, blank=True, null=True)
    deal = models.ForeignKey(Deal, verbose_name='Сделка', on_delete=models.CASCADE, related_name='deal_course',blank=True, null=True)


    class Meta:
        db_table = 'operation_deal_course'
        ordering = ['id']
        verbose_name = 'Изменение курса'
        verbose_name_plural = 'Изменение курсов'

    def __str__(self):
        return str(self.id)

class HistoryBill(models.Model):
    income_before = models.DecimalField('Приход до',max_digits=18, decimal_places=8, default=0.00, blank=True, null=True)
    income_after = models.DecimalField('Приход после',max_digits=18, decimal_places=8,default=0.00, blank=True, null=True)
    expense_before = models.DecimalField('Расход до', max_digits=18, decimal_places=8, default=0.00, blank=True,
                                        null=True)
    expense_after = models.DecimalField('Расход после', max_digits=18, decimal_places=8, default=0.00, blank=True,
                                       null=True)
    in_ex = models.ForeignKey(IncomeExpense, verbose_name='Пара', on_delete=models.CASCADE, related_name='in_ex_history',blank=True, null=True)


    class Meta:
        db_table = 'operation_in_ex_history'
        ordering = ['id']
        verbose_name = 'История балансов'
        verbose_name_plural = 'Истории балансов'

    def __str__(self):
        return str(self.id)


class LogOperation(models.Model):
    data = models.CharField('Наименование', max_length=1024)

    class Meta:
        db_table = 'operation_logs'
        ordering = ['id']
        verbose_name = 'Лог'
        verbose_name_plural = 'Логи'

    def __str__(self):
        return str(self.id)


class PercentCourse(models.Model):
    value = models.FloatField('Значение', blank=True, null=True)

    class Meta:
        db_table = 'operation_percent'
        ordering = ['id']
        verbose_name = 'Процент'
        verbose_name_plural = 'Проценты'

    def __str__(self):
        return str(self.value)

class CourseHistory(models.Model):
    old_value = models.FloatField('Новое значение', blank=True, null=True)
    new_value = models.FloatField('Старое значение', blank=True, null=True)
    currency = models.ForeignKey(Currency,verbose_name='Валюта',on_delete=models.SET_NULL,null=True)

    class Meta:
        db_table = 'operation_course_history'
        ordering = ['id']
        verbose_name = 'История курса'
        verbose_name_plural = 'История курсов'

    def __str__(self):
        return str(self.value)





	


from django.db import models
from decimal import Decimal, ROUND_HALF_UP
#from operation.models import Deal
from django.utils import timezone


# Create your models here.
class Currency(models.Model):
    name = models.CharField('Наименование', max_length=255)
    short_name = models.CharField('Краткое наименование', max_length=64, blank=True, null=True)
    zeros_after = models.IntegerField(verbose_name='Нолей после запятой', default=2)
    zeros_after_rate = models.IntegerField(verbose_name='Курс, нолей после запятой', default=2)
    rate = models.DecimalField('Курс', max_digits=18, decimal_places=8, default=0.00, blank=True, null=True)
    status = models.BooleanField('Статус', default=True)

    class Meta:
        db_table = 'catalog_currencys'
        ordering = ['id']
        verbose_name = 'Валюта'
        verbose_name_plural = 'Валюты'

    def __str__(self):
        return self.short_name


class Bill(models.Model):
    name = models.CharField('Наименование', max_length=255)
    short_name = models.CharField('Краткое наименование', max_length=64, blank=True, null=True)
    currency = models.ForeignKey(Currency, verbose_name='Валюта', on_delete=models.SET_NULL, related_name='currency_bills',blank=True, null=True)
    status = models.BooleanField('Статус', default=True)
    remainder = models.DecimalField('Остаток',max_digits=18, decimal_places=8,default=0.00)
    initial_remainder = models.DecimalField('Первоначальный остаток',max_digits=18, decimal_places=8,default=0.00)
    rate = models.DecimalField('Курс',max_digits=18, decimal_places=8,default=0.00, blank=True, null=True)
    initial_rate = models.DecimalField('Первоначальный курс',max_digits=18, decimal_places=8,default=0.00, blank=True, null=True)
    old_rate = models.DecimalField('Старый курс',max_digits=18, decimal_places=8,default=0.00, blank=True, null=True)

    class Meta:
        db_table = 'catalog_bills'
        ordering = ['id']
        verbose_name = 'Счет'
        verbose_name_plural = 'Счета'

    def __str__(self):
        return self.short_name


    def save(self, *args, **kwargs):
        if self.pk is None and (self.initial_rate is None or self.initial_rate == 0.00):
            self.initial_rate = self.rate
            self.initial_remainder = self.remainder
        super().save(*args, **kwargs)

class Contractor(models.Model):
    name = models.CharField('Имя', max_length=255)
    status = models.BooleanField('Статус', default=True)
    duty = models.DecimalField('Баланс',max_digits=18, decimal_places=8,default=0.00)
    duty_usdt = models.DecimalField('Баланс USDT', max_digits=18, decimal_places=8, default=0.00)

    class Meta:
        db_table = 'catalog_contractors'
        ordering = ['id']
        verbose_name = 'Контрагент'
        verbose_name_plural = 'Контрагенты'

    def __str__(self):
        return self.name

class ContractorHistory(models.Model):
    duty = models.DecimalField('Баланс', max_digits=18, decimal_places=8, default=0.00)
    duty_usdt = models.DecimalField('Баланс USDT', max_digits=18, decimal_places=8, blank=True, null=True)
    duty_cost = models.DecimalField('Баланс себестоимости', max_digits=18, decimal_places=8, null=True, blank=True)
    contractor = models.ForeignKey(Contractor, verbose_name='Контрагент', on_delete=models.CASCADE, related_name='contractor_history',
                             blank=True, null=True)
    deal = models.ForeignKey('operation.Deal', verbose_name='Сделка', on_delete=models.CASCADE,
                                   related_name='contractor_deal',
                                   blank=True, null=True)
    date_create = models.DateTimeField('Дата создания', blank=True, null=True, default=timezone.now)

    class Meta:
        db_table = 'catalog_contractors_history'
        ordering = ['id']
        verbose_name = 'История контрагента'
        verbose_name_plural = 'История контрагентов'

    def __str__(self):
        return self.contractor.name

class CashFlow(models.Model):
    TYPE_INCOME = 'income'
    TYPE_EXPENSE = 'expense'
    TYPE_CHOICES = [
        (TYPE_INCOME, 'Приход'),
        (TYPE_EXPENSE, 'Расход'),
    ]

    name = models.CharField('Имя', max_length=255)
    type_cf = models.CharField(
        verbose_name='Тип ДДС',
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_INCOME
    )
    status = models.BooleanField('Статус', default=True)

    class Meta:
        db_table = 'catalog_cashflows'
        ordering = ['id']
        verbose_name = 'ДДС'
        verbose_name_plural = 'ДДС'

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField('Наименование', max_length=255)
    status = models.BooleanField('Статус', default=True)

    class Meta:
        db_table = 'catalog_categorys'
        ordering = ['id']
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name




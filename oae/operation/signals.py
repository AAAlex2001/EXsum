from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from .models import Deal, IncomeExpense, CourseBill, LogOperation
from .utils import get_weighted_avg_rate, get_total_rate_balance
from django.db import transaction
from django.contrib import messages
from threading import local
import time
import random
from django.core.exceptions import ValidationError


@receiver(pre_save, sender=IncomeExpense)
def in_ex_presave(sender, instance, **kwargs):
	if not instance._state.adding:
		try:
			old_instance = sender.objects.get(pk=instance.pk)
		except sender.DoesNotExist:
			old_instance = None
		if old_instance:
			try:
				if old_instance.expense_amount != instance.expense_amount and instance.expense_amount > old_instance.expense_amount:
					new_amount = instance.expense_amount - old_instance.expense_amount
					if new_amount > instance.expense_account.remainder:
						raise ValidationError("Недостаточно средств на счете {0}".format(instance.expense_account))
			except:
				pass
	else:
		try:
			if instance.expense_account and instance.expense_amount > instance.expense_account.remainder:
				raise ValidationError("Недостаточно средств на счете {0}".format(instance.expense_account))
		except:
			pass


@receiver(post_delete, sender=IncomeExpense)
def in_ex_postdelete(sender, instance, **kwargs):
	try:
		income_account = instance.income_account
		if income_account and IncomeExpense.objects.filter(income_account=income_account).count() == 0:
			income_account.rate = income_account.initial_rate
			income_account.remainder = income_account.initial_remainder
			income_account.save()
		expense_account = instance.expense_account
		if expense_account and IncomeExpense.objects.filter(expense_account=expense_account).count() == 0:
			expense_account.rate = expense_account.initial_rate
			expense_account.remainder = expense_account.initial_remainder
			expense_account.save()
	except:
		pass



		




from django import forms
from datetime import datetime, time
from django.utils.timezone import make_aware, get_default_timezone
import django.utils.timezone as timezone

class DateRangeForm(forms.Form):
    date_from = forms.DateTimeField(
        label="Дата от",
        required=False,
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'form-input block w-full rounded-md border-gray-300 shadow-sm'
            }
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
        initial=timezone.datetime(timezone.now().year, 1, 1, 0, 0)
    )
    date_to = forms.DateTimeField(
        label="Дата до",
        required=False,
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'form-input block w-full rounded-md border-gray-300 shadow-sm'
            }
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
        initial=timezone.datetime(
                timezone.now().year,
                timezone.now().month,
                timezone.now().day,
                23, 59
            )#timezone.now
    )

    


class TypeForm(forms.Form):
    type = forms.ChoiceField(
        label="Вид",
        choices=[
            #("", "Все"),
            ("aggregates", "Агрегаты"),
            ("delivery", "Доставка"),
        ],
        widget=forms.Select(attrs={
            "class": "appearance-none w-full bg-white border border-green-500 text-gray-900 py-2 px-3 pr-10 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500 sm:text-sm"
        })
    )
    bill_type = forms.ChoiceField(
        label="Счет",
        choices=[
            ("uae", "ОАЭ"),
            ("kor", "Корея"),
            ("installment", "Выручка агрегаты рассрочка"),
            ("installment_20", "Выручка агрегаты рассрочка 20%"),
        ],
        widget=forms.Select(attrs={
            "class": "appearance-none w-full bg-white border border-green-500 text-gray-900 py-2 px-3 pr-10 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500 sm:text-sm"
        })
    )
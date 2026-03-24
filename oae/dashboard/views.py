from django.shortcuts import render
from django.http import JsonResponse
from catalog.models import Contractor, ContractorHistory
from operation.models import PercentCourse
import requests
from django.http import HttpResponse
from decimal import Decimal, ROUND_HALF_UP

def ip_view(request):
    contractor = Contractor.objects.get(id=1)
    last_dutys = ContractorHistory.objects.filter(contractor=contractor)
    if last_dutys.count() != 0:
        duty = float(last_dutys.last().duty)
    else:
        duty = 0
    return render(request, 'ip_view.html', {
        'contractor_name': contractor.name,
        'contractor_duty': duty,
    })


def courses_view(request):
    url = 'https://api.rapira.net/open/market/rates'
    try:
        r = requests.get(url, timeout=2)
        r.raise_for_status()
        data = r.json()
        course_percent = PercentCourse.objects.first().value
        course_main = Decimal(data['data'][0]['close'])
        course_base= course_main * (Decimal(1 + (course_percent / 100)))
        course_tadg = course_base + 3
        course_delivery = course_main * (Decimal(1 + (3 / 100)))
    except Exception as e:
        return HttpResponse(f"Ошибка при получении курсов: {str(e)}", status=500)
        course_base = 0
        course_tadg = 0
    return render(request, 'course_view.html', {
        'course_base': course_base,
        'course_tadg': course_tadg,
        'course_delivery': float(course_delivery),
    })

def get_courses_view(request):
    url = 'https://api.rapira.net/open/market/rates'
    try:
        r = requests.get(url, timeout=2)
        r.raise_for_status()
        data = r.json()
        course_percent = PercentCourse.objects.first().value
        course_main = Decimal(data['data'][0]['close'])
        course_base = course_main * (Decimal(1 + (course_percent / 100)))
        course_tj = course_base + Decimal(3)
        course_base = course_base.quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)
        course_tj = course_tj.quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)

    except Exception as e:
        return HttpResponse(f"Ошибка при получении курсов: {str(e)}", status=500)
        course_base = 0
        course_tadg = 0
    return JsonResponse({
        'course_basic': float(course_base),
        'course_tj': float(course_tj),

    })
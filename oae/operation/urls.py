from django.urls import path, re_path, include
from django.views.decorators.csrf import csrf_exempt
from . import views
from rest_framework import permissions
from django.conf import settings
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'operations', views.IncomeExpenseViewSet, basename='operations')
#router.register(r'check_autocomplete', views.CheckAutocomplete, basename='check_autocomplete')

urlpatterns = router.urls
urlpatterns += [path('check_autocomplete/', views.CheckAutocomplete.as_view()),]
urlpatterns += [path('check_national_currency/', views.CheckNationalCurrency.as_view()),]
urlpatterns += [path('get_cashflow_balance/', views.GetCashflowBalance.as_view()),]
urlpatterns += [path('get_rate_info/', views.GetRateInfo.as_view()),]
urlpatterns += [path('get_war_balance/', views.GetWarBalance.as_view()),]
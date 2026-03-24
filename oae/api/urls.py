from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework import permissions
from django.conf import settings


urlpatterns = [
    path('operation/', include('operation.urls')),
]
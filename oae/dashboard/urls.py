from django.urls import path
from .views import ip_view, courses_view, get_courses_view

urlpatterns = [
    path('ip/', ip_view, name='ip'),
    path('courses/', courses_view, name='courses'),
    path('get_courses/', get_courses_view, name='get_courses'),
]
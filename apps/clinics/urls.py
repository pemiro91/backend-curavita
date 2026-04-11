# apps/clinics/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ClinicViewSet, DoctorViewSet

router = DefaultRouter()
router.register(r'', ClinicViewSet, basename='clinic')
router.register(r'doctors', DoctorViewSet, basename='doctor')

urlpatterns = [
    path('', include(router.urls)),
]
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    SpecialtyViewSet,
    ServiceViewSet,
    ServiceByClinicView,
    SpecialtyListView,
    ServiceBySpecialtyView
)

router = DefaultRouter()
router.register(r'specialties', SpecialtyViewSet, basename='specialty')
router.register(r'', ServiceViewSet, basename='service')

urlpatterns = [
    path('specialties/list/', SpecialtyListView.as_view(), name='specialty-list'),
    path('clinic/<uuid:clinic_id>/', ServiceByClinicView.as_view(), name='services-by-clinic'),
    path('', include(router.urls)),
    path('specialties/<uuid:specialty_id>/', ServiceBySpecialtyView.as_view(), name='specialty-services'),
]

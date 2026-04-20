from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    ClinicViewSet,
    DoctorViewSet,
    ClinicImageViewSet,
    NearbyClinicsView,
    ClinicSearchView,
    DoctorScheduleView,
    AvailableSlotsView,
    ClinicStatsView,
)

# Router principal
router = DefaultRouter()
router.register(r'', ClinicViewSet, basename='clinic')
router.register(r'doctors', DoctorViewSet, basename='doctor')

# Router anidado para imágenes de clínicas
# Esto crea rutas como /clinics/{clinic_pk}/images/
clinics_router = routers.NestedSimpleRouter(router, r'', lookup='clinic')
clinics_router.register(r'images', ClinicImageViewSet, basename='clinic-images')

urlpatterns = [
    # Rutas del router principal y anidado
    path('', include(router.urls)),
    path('', include(clinics_router.urls)),

    # Vistas adicionales de búsqueda y geolocalización
    path('nearby/', NearbyClinicsView.as_view(), name='clinics-nearby'),
    path('search/', ClinicSearchView.as_view(), name='clinics-search'),

    # path('<slug:slug>/', ClinicDetailView.as_view(), name='clinic-detail'),

    # Rutas específicas de doctores (vistas adicionales)
    path('doctors/<uuid:pk>/schedule/',
         DoctorScheduleView.as_view(), name='doctor-schedule'),
    path('doctors/<uuid:pk>/slots/',
         AvailableSlotsView.as_view(), name='doctor-available-slots'),
    path('doctors/<uuid:pk>/stats/',
         ClinicStatsView.as_view(), name='doctor-stats'),
]

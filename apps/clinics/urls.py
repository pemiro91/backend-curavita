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
    DoctorRegistrationView,
    ClinicRegisterView,
    ClinicMeView,
    ClinicRejectView,
    ClinicMeImagesView,
    ClinicMeStatsView
)

# Router principal
# IMPORTANT: register 'doctors' BEFORE '' so the slug-lookup of ClinicViewSet
# (pattern ^(?P<slug>[^/.]+)/$ ) doesn't swallow /doctors/ as a clinic detail,
# which would return 405 on POST (detail view doesn't accept POST).
router = DefaultRouter()
router.register(r'doctors', DoctorViewSet, basename='doctor')
router.register(r'', ClinicViewSet, basename='clinic')

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
    path('register/', ClinicRegisterView.as_view(), name='clinic-register'),
    path('me/', ClinicMeView.as_view(), name='clinic-me'),
    path('me/images/', ClinicMeImagesView.as_view(), name='clinic-me-images'),
    path('me/stats/', ClinicMeStatsView.as_view(), name='clinic-me-stats'),
    # Rechazo de solicitud (slug-based, debe ir DESPUÉS de rutas /me/)
    path('<slug:slug>/reject/', ClinicRejectView.as_view(), name='clinic-reject'),
    # adaptar ClinicStatsView para usar clinic del admin
    # path('<slug:slug>/', ClinicDetailView.as_view(), name='clinic-detail'),

    # Rutas específicas de doctores (vistas adicionales)
    path('doctors/<uuid:pk>/schedule/',
         DoctorScheduleView.as_view(), name='doctor-schedule'),
    path('doctors/<uuid:pk>/slots/',
         AvailableSlotsView.as_view(), name='doctor-available-slots'),
    path('doctors/<uuid:pk>/stats/',
         ClinicStatsView.as_view(), name='doctor-stats'),
    path('doctors/register/', DoctorRegistrationView.as_view(), name='doctor-register'),
]

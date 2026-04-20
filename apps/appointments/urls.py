# apps/appointments/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'appointments', views.AppointmentViewSet, basename='appointment')
router.register(r'time-slots', views.TimeSlotViewSet, basename='timeslot')

urlpatterns = [
    path('', include(router.urls)),

    # Vistas adicionales
    path('my-appointments/', views.MyAppointmentsView.as_view(), name='my-appointments'),
    path('upcoming/', views.UpcomingAppointmentsView.as_view(), name='upcoming-appointments'),
    path('past/', views.PastAppointmentsView.as_view(), name='past-appointments'),
    path('stats/', views.AppointmentStatsView.as_view(), name='appointment-stats'),

    # Acciones sobre citas
    path('<uuid:pk>/cancel/', views.CancelAppointmentView.as_view(), name='cancel-appointment'),
    path('<uuid:pk>/reschedule/', views.RescheduleAppointmentView.as_view(), name='reschedule-appointment'),
    path('<uuid:pk>/confirm/', views.ConfirmAppointmentView.as_view(), name='confirm-appointment'),
    path('<uuid:pk>/complete/', views.CompleteAppointmentView.as_view(), name='complete-appointment'),
    path('<uuid:pk>/check-in/', views.CheckInAppointmentView.as_view(), name='check-in-appointment'),
    path('<uuid:pk>/history/', views.AppointmentHistoryView.as_view(), name='appointment-history'),

    # Consulta de slots disponibles
    path('available-slots/', views.AvailableSlotsView.as_view(), name='available-slots'),
]

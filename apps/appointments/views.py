import logging
from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from datetime import datetime, timedelta

from .models import Appointment, TimeSlot, AppointmentHistory
from .serializers import (
    AppointmentListSerializer,
    AppointmentDetailSerializer,
    AppointmentCreateSerializer,
    AppointmentUpdateSerializer,
    TimeSlotSerializer,
    TimeSlotCreateSerializer,
    AppointmentHistorySerializer,
    AvailableSlotsQuerySerializer,
)
from .permissions import IsAppointmentParticipant

logger = logging.getLogger(__name__)


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de citas médicas.
    """
    queryset = Appointment.objects.all()
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'clinic', 'doctor', 'date']
    ordering_fields = ['date', 'start_time', 'created_at']
    ordering = ['-date', '-start_time']

    def get_serializer_class(self):
        if self.action == 'create':
            return AppointmentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return AppointmentUpdateSerializer
        elif self.action == 'retrieve':
            return AppointmentDetailSerializer
        return AppointmentListSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAppointmentParticipant()]

    def get_queryset(self):
        user = self.request.user

        if user.user_type == 'super_admin':
            return Appointment.objects.all()
        elif user.user_type == 'clinic_admin':
            return Appointment.objects.filter(clinic__admins=user)
        elif user.user_type == 'doctor':
            return Appointment.objects.filter(doctor__user=user)
        else:
            return Appointment.objects.filter(patient=user)

    def perform_create(self, serializer):
        serializer.save(patient=self.request.user)

    @action(detail=False, methods=['get'])
    def my_appointments(self, request):
        """Obtener citas del usuario actual"""
        appointments = self.get_queryset().filter(
            patient=request.user
        )[:50]
        serializer = AppointmentListSerializer(appointments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Obtener próximas citas"""
        appointments = self.get_queryset().filter(
            date__gte=timezone.now().date(),
            status__in=['pending', 'confirmed']
        ).order_by('date', 'start_time')[:10]

        serializer = AppointmentListSerializer(appointments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def past(self, request):
        """Obtener citas pasadas"""
        appointments = self.get_queryset().filter(
            Q(date__lt=timezone.now().date()) |
            Q(status__in=['completed', 'cancelled', 'no_show'])
        ).order_by('-date')[:50]

        serializer = AppointmentListSerializer(appointments, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancelar una cita"""
        appointment = self.get_object()

        if not appointment.can_cancel:
            return Response(
                {'error': 'Esta cita no puede ser cancelada.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', 'patient_request')
        notes = request.data.get('notes', '')

        appointment.status = 'cancelled'
        appointment.cancelled_by = request.user
        appointment.cancellation_reason = reason
        appointment.cancellation_notes = notes
        appointment.cancelled_at = timezone.now()
        appointment.save()

        # Liberar horario
        TimeSlot.objects.filter(
            doctor=appointment.doctor,
            date=appointment.date,
            start_time=appointment.start_time
        ).update(is_available=True)

        return Response({'message': 'Cita cancelada correctamente.'})

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirmar una cita"""
        appointment = self.get_object()

        if appointment.status != 'pending':
            return Response(
                {'error': 'Solo se pueden confirmar citas pendientes.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Solo admin de clínica o el doctor pueden confirmar
        if request.user not in appointment.clinic.admins.all() and \
                request.user != appointment.doctor.user:
            raise PermissionDenied('No tienes permiso para confirmar esta cita.')

        appointment.status = 'confirmed'
        appointment.save()

        return Response({'message': 'Cita confirmada correctamente.'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Marcar cita como completada"""
        appointment = self.get_object()

        if appointment.status not in ['confirmed', 'checked_in', 'in_progress']:
            return Response(
                {'error': 'No se puede completar esta cita.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        appointment.status = 'completed'
        appointment.save()

        return Response({'message': 'Cita completada correctamente.'})

    @action(detail=True, methods=['post'])
    def check_in(self, request, pk=None):
        """Realizar check-in de la cita"""
        appointment = self.get_object()

        if appointment.status != 'confirmed':
            return Response(
                {'error': 'Solo se puede hacer check-in de citas confirmadas.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        appointment.status = 'checked_in'
        appointment.save()

        return Response({'message': 'Check-in realizado correctamente.'})

    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        """Reagendar una cita"""
        appointment = self.get_object()

        if not appointment.can_reschedule:
            return Response(
                {'error': 'Esta cita no puede ser reagendada.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_date = request.data.get('date')
        new_time = request.data.get('start_time')

        if not new_date or not new_time:
            return Response(
                {'error': 'Se requieren date y start_time.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Liberar horario anterior
        TimeSlot.objects.filter(
            doctor=appointment.doctor,
            date=appointment.date,
            start_time=appointment.start_time
        ).update(is_available=True)

        # Actualizar cita
        appointment.date = new_date
        appointment.start_time = new_time
        appointment.status = 'pending'
        appointment.save()

        # Bloquear nuevo horario
        TimeSlot.objects.filter(
            doctor=appointment.doctor,
            date=new_date,
            start_time=new_time
        ).update(is_available=False)

        return Response({'message': 'Cita reagendada correctamente.'})

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Obtener historial de cambios de una cita"""
        appointment = self.get_object()
        history = appointment.history.all()
        serializer = AppointmentHistorySerializer(history, many=True)
        return Response(serializer.data)


class TimeSlotViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de horarios disponibles.
    """
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['doctor', 'date', 'is_available']

    def get_serializer_class(self):
        if self.action == 'create':
            return TimeSlotCreateSerializer
        return TimeSlotSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]  # Solo clínicas pueden modificar


class MyAppointmentsView(generics.ListAPIView):
    """
    Vista para listar citas del usuario actual.
    """
    serializer_class = AppointmentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Appointment.objects.filter(patient=self.request.user)


class UpcomingAppointmentsView(generics.ListAPIView):
    """
    Vista para listar próximas citas.
    """
    serializer_class = AppointmentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Appointment.objects.filter(
            patient=self.request.user,
            date__gte=timezone.now().date(),
            status__in=['pending', 'confirmed']
        ).order_by('date', 'start_time')


class PastAppointmentsView(generics.ListAPIView):
    """
    Vista para listar citas pasadas.
    """
    serializer_class = AppointmentListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Appointment.objects.filter(
            patient=self.request.user
        ).filter(
            Q(date__lt=timezone.now().date()) |
            Q(status__in=['completed', 'cancelled', 'no_show'])
        ).order_by('-date')


class CancelAppointmentView(generics.GenericAPIView):
    """
    Vista para cancelar una cita.
    """
    permission_classes = [IsAuthenticated, IsAppointmentParticipant]

    def post(self, request, pk):
        appointment = Appointment.objects.get(id=pk)

        if not appointment.can_cancel:
            return Response(
                {'error': 'Esta cita no puede ser cancelada.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', 'patient_request')
        notes = request.data.get('notes', '')

        appointment.status = 'cancelled'
        appointment.cancelled_by = request.user
        appointment.cancellation_reason = reason
        appointment.cancellation_notes = notes
        appointment.cancelled_at = timezone.now()
        appointment.save()

        return Response({'message': 'Cita cancelada correctamente.'})


class RescheduleAppointmentView(generics.GenericAPIView):
    """
    Vista para reagendar una cita.
    """
    permission_classes = [IsAuthenticated, IsAppointmentParticipant]

    def post(self, request, pk):
        appointment = Appointment.objects.get(id=pk)

        if not appointment.can_reschedule:
            return Response(
                {'error': 'Esta cita no puede ser reagendada.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_date = request.data.get('date')
        new_time = request.data.get('start_time')

        appointment.date = new_date
        appointment.start_time = new_time
        appointment.status = 'pending'
        appointment.save()

        return Response({'message': 'Cita reagendada correctamente.'})


class ConfirmAppointmentView(generics.GenericAPIView):
    """
    Vista para confirmar una cita.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        appointment = Appointment.objects.get(id=pk)

        if request.user not in appointment.clinic.admins.all() and \
                request.user != appointment.doctor.user:
            raise PermissionDenied()

        appointment.status = 'confirmed'
        appointment.save()

        return Response({'message': 'Cita confirmada correctamente.'})


class CompleteAppointmentView(generics.GenericAPIView):
    """
    Vista para completar una cita.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        appointment = Appointment.objects.get(id=pk)
        appointment.status = 'completed'
        appointment.save()
        return Response({'message': 'Cita completada correctamente.'})


class CheckInAppointmentView(generics.GenericAPIView):
    """
    Vista para check-in de una cita.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        appointment = Appointment.objects.get(id=pk)
        appointment.status = 'checked_in'
        appointment.save()
        return Response({'message': 'Check-in realizado correctamente.'})


class AppointmentHistoryView(generics.ListAPIView):
    """
    Vista para ver historial de una cita.
    """
    serializer_class = AppointmentHistorySerializer
    permission_classes = [IsAuthenticated, IsAppointmentParticipant]

    def get_queryset(self):
        appointment_id = self.kwargs['pk']
        return AppointmentHistory.objects.filter(appointment_id=appointment_id)


class AvailableSlotsView(generics.GenericAPIView):
    """
    Vista para consultar horarios disponibles.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AvailableSlotsQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doctor_id = serializer.validated_data['doctor_id']
        date = serializer.validated_data['date']

        from apps.clinics.models import Doctor

        try:
            doctor = Doctor.objects.get(id=doctor_id)
        except Doctor.DoesNotExist:
            return Response(
                {'error': 'Médico no encontrado.'},
                status=status.HTTP_404_NOT_FOUND
            )

        slots = TimeSlot.objects.filter(
            doctor=doctor,
            date=date,
            is_available=True,
            is_blocked=False
        ).order_by('start_time')

        return Response(TimeSlotSerializer(slots, many=True).data)


class AppointmentStatsView(generics.GenericAPIView):
    """
    Vista para estadísticas de citas.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.user_type == 'patient':
            total = Appointment.objects.filter(patient=user).count()
            completed = Appointment.objects.filter(patient=user, status='completed').count()
            cancelled = Appointment.objects.filter(patient=user, status='cancelled').count()
        elif user.user_type == 'doctor':
            total = Appointment.objects.filter(doctor__user=user).count()
            completed = Appointment.objects.filter(doctor__user=user, status='completed').count()
            cancelled = Appointment.objects.filter(doctor__user=user, status='cancelled').count()
        else:
            total = Appointment.objects.filter(clinic__admins=user).count()
            completed = Appointment.objects.filter(clinic__admins=user, status='completed').count()
            cancelled = Appointment.objects.filter(clinic__admins=user, status='cancelled').count()

        return Response({
            'total_appointments': total,
            'completed_appointments': completed,
            'cancelled_appointments': cancelled,
            'completion_rate': round(completed / total * 100, 2) if total > 0 else 0
        })

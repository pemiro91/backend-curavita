import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from apps.users.models import User
from apps.clinics.models import Clinic, Doctor
from apps.services.models import Service


class Appointment(models.Model):
    """Modelo de Cita Médica"""

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pendiente')
        CONFIRMED = 'confirmed', _('Confirmada')
        CHECKED_IN = 'checked_in', _('Check-in Realizado')
        IN_PROGRESS = 'in_progress', _('En Atención')
        COMPLETED = 'completed', _('Completada')
        CANCELLED = 'cancelled', _('Cancelada')
        NO_SHOW = 'no_show', _('No Asistió')

    class CancellationReason(models.TextChoices):
        PATIENT_REQUEST = 'patient_request', _('Solicitud del Paciente')
        DOCTOR_UNAVAILABLE = 'doctor_unavailable', _('Médico No Disponible')
        CLINIC_CLOSED = 'clinic_closed', _('Clínica Cerrada')
        EMERGENCY = 'emergency', _('Emergencia')
        OTHER = 'other', _('Otro')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment_number = models.CharField(max_length=20, unique=True, editable=False)

    # Relaciones
    patient = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='appointments',
        limit_choices_to={'user_type': 'patient'}
    )
    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='appointments')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='appointments')

    # Fecha y hora
    date = models.DateField(_('date'))
    start_time = models.TimeField(_('start time'))
    end_time = models.TimeField(_('end time'), editable=False)

    # Estado
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # Cancelación
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_appointments'
    )
    cancellation_reason = models.CharField(
        _('cancellation reason'),
        max_length=30,
        choices=CancellationReason.choices,
        blank=True
    )
    cancellation_notes = models.TextField(_('cancellation notes'), blank=True)

    # Notas
    patient_notes = models.TextField(_('patient notes'), blank=True)
    doctor_notes = models.TextField(_('doctor notes'), blank=True)
    internal_notes = models.TextField(_('internal notes'), blank=True)

    # Recordatorios
    reminder_sent_24h = models.BooleanField(default=False)
    reminder_sent_1h = models.BooleanField(default=False)

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('appointment')
        verbose_name_plural = _('appointments')
        ordering = ['-date', '-start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'date', 'start_time'],
                name='unique_doctor_appointment_time'
            ),
        ]

    def __str__(self):
        return f"#{self.appointment_number} - {self.patient.full_name} con Dr. {self.doctor.user.full_name}"

    def save(self, *args, **kwargs):
        # Generar número de cita
        if not self.appointment_number:
            self.appointment_number = self.generate_appointment_number()

        # Calcular end_time
        if self.service and self.start_time:
            from datetime import datetime, timedelta
            start_datetime = datetime.combine(self.date, self.start_time)
            end_datetime = start_datetime + timedelta(minutes=self.service.duration_minutes)
            self.end_time = end_datetime.time()

        super().save(*args, **kwargs)

    def generate_appointment_number(self):
        """Generar número único de cita: APT-YYYYMMDD-XXXX"""
        from datetime import datetime
        today = datetime.now()
        prefix = f"APT-{today.strftime('%Y%m%d')}"

        # Contar citas del día
        count = Appointment.objects.filter(
            appointment_number__startswith=prefix
        ).count()

        return f"{prefix}-{count + 1:04d}"

    def clean(self):
        # Validar que la fecha no sea en el pasado
        if self.date and self.date < timezone.now().date():
            raise ValidationError(_('La fecha de la cita no puede ser en el pasado.'))

        # Validar que el doctor pertenezca a la clínica
        if self.doctor and self.clinic and self.doctor.clinic != self.clinic:
            raise ValidationError(_('El médico no pertenece a esta clínica.'))

        # Validar que el servicio pertenezca a la clínica
        if self.service and self.clinic and self.service.clinic != self.clinic:
            raise ValidationError(_('El servicio no pertenece a esta clínica.'))

    @property
    def can_cancel(self):
        """Verificar si la cita puede ser cancelada"""
        return self.status in ['pending', 'confirmed']

    @property
    def can_reschedule(self):
        """Verificar si la cita puede ser reagendada"""
        return self.status in ['pending', 'confirmed']


class TimeSlot(models.Model):
    """Horarios disponibles para citas"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='time_slots')

    date = models.DateField(_('date'))
    start_time = models.TimeField(_('start time'))
    end_time = models.TimeField(_('end time'))

    is_available = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)  # Bloqueado por admin
    blocked_reason = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('time slot')
        verbose_name_plural = _('time slots')
        ordering = ['date', 'start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'date', 'start_time'],
                name='unique_time_slot'
            ),
        ]

    def __str__(self):
        return f"{self.doctor} - {self.date} {self.start_time}"


class AppointmentHistory(models.Model):
    """Historial de cambios en citas"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='history')

    action = models.CharField(max_length=50)  # created, updated, cancelled, etc.
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)

    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('appointment history')
        verbose_name_plural = _('appointment histories')
        ordering = ['-created_at']

# apps/appointments/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from apps.clinics.models import Doctor
from .utils import generate_slots_from_schedule, cleanup_old_slots


@shared_task
def generate_daily_slots():
    """
    Tarea diaria para generar slots para los próximos días.
    Ejecutar con: celery -A config beat -l info
    """
    doctors = Doctor.objects.filter(status='active')

    # Generar slots para los próximos 7 días (ventana móvil)
    start = timezone.now().date() + timedelta(days=14)  # 2 semanas adelante
    end = start + timedelta(days=7)

    total_created = 0
    for doctor in doctors:
        count = generate_slots_from_schedule(
            doctor,
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d')
        )
        total_created += count

    return f"Generated {total_created} slots for {doctors.count()} doctors"


@shared_task
def cleanup_expired_slots():
    """Eliminar slots antiguos"""
    count = cleanup_old_slots(days_past=30)
    return f"Deleted {count} expired slots"


@shared_task
def send_appointment_reminder(appointment_id):
    """
    Enviar recordatorio de cita (24h o 1h antes)
    """
    from .models import Appointment
    from apps.notifications.models import Notification

    try:
        appointment = Appointment.objects.get(id=appointment_id)

        if appointment.status not in ['pending', 'confirmed']:
            return "Appointment not active"

        # Determinar qué recordatorio es
        now = timezone.now()
        apt_datetime = timezone.make_aware(
            timezone.datetime.combine(appointment.date, appointment.start_time)
        )
        hours_until = (apt_datetime - now).total_seconds() / 3600

        if 23 <= hours_until <= 25:
            # Recordatorio 24h
            appointment.reminder_sent_24h = True
            notification_type = 'appointment_reminder_24h'
            title = 'Recordatorio: Tu cita es mañana'
        elif 0.5 <= hours_until <= 1.5:
            # Recordatorio 1h
            appointment.reminder_sent_1h = True
            notification_type = 'appointment_reminder_1h'
            title = 'Recordatorio: Tu cita es en 1 hora'
        else:
            return "Not the right time for reminder"

        appointment.save()

        # Crear notificación
        Notification.objects.create(
            recipient=appointment.patient,
            notification_type=notification_type,
            channel='email',
            title=title,
            message=f'Tu cita con Dr. {appointment.doctor.user.full_name} en {appointment.clinic.name} es el {appointment.date} a las {appointment.start_time}.',
            action_url=f'/appointments/{appointment.id}'
        )

        return f"Reminder sent for appointment {appointment_id}"

    except Appointment.DoesNotExist:
        return "Appointment not found"
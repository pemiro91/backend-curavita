# apps/notifications/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

from .models import Notification


@shared_task
def send_appointment_reminder(appointment_id):
    """Enviar recordatorio de cita"""
    from apps.appointments.models import Appointment

    try:
        appointment = Appointment.objects.get(id=appointment_id)

        # Crear notificación
        Notification.objects.create(
            recipient=appointment.patient,
            notification_type='appointment_reminder',
            channel='email',
            title=f'Recordatorio: Cita con Dr. {appointment.doctor.user.full_name}',
            message=f'Tienes una cita programada para el {appointment.date} a las {appointment.start_time}.',
            action_url=f'/appointments/{appointment.id}'
        )

        # Enviar email
        send_mail(
            subject=f'Recordatorio de Cita - {appointment.clinic.name}',
            message=f'''
            Hola {appointment.patient.first_name},

            Te recordamos que tienes una cita programada:

            📅 Fecha: {appointment.date}
            ⏰ Hora: {appointment.start_time}
            🏥 Clínica: {appointment.clinic.name}
            👨‍⚕️ Médico: Dr. {appointment.doctor.user.full_name}
            📋 Servicio: {appointment.service.name}

            Dirección: {appointment.clinic.street}, {appointment.clinic.number}

            ¡Te esperamos!
            ''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[appointment.patient.email],
        )

    except Appointment.DoesNotExist:
        pass
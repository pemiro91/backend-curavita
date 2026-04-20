import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import Appointment, TimeSlot, AppointmentHistory

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Appointment)
def create_appointment_history(sender, instance, created, **kwargs):
    """
    Crear registro en el historial de citas
    """
    if created:
        AppointmentHistory.objects.create(
            appointment=instance,
            action='created',
            new_status=instance.status,
            performed_by=instance.patient,
            notes='Cita creada por el paciente'
        )
        logger.info(f"Historial creado para cita {instance.appointment_number}")
    else:
        # Si cambió el estado, registrar el cambio
        if hasattr(instance, '_previous_status') and instance._previous_status != instance.status:
            AppointmentHistory.objects.create(
                appointment=instance,
                action='status_changed',
                previous_status=instance._previous_status,
                new_status=instance.status
            )


@receiver(pre_save, sender=Appointment)
def store_appointment_previous_state(sender, instance, **kwargs):
    """
    Guardar estado anterior de la cita
    """
    if instance.pk:
        try:
            old_appointment = Appointment.objects.get(pk=instance.pk)
            instance._previous_status = old_appointment.status
        except Appointment.DoesNotExist:
            pass


@receiver(post_save, sender=Appointment)
def manage_time_slot_on_appointment(sender, instance, created, **kwargs):
    """
    Gestionar disponibilidad del horario según el estado de la cita
    """
    if created:
        # Bloquear el horario
        TimeSlot.objects.filter(
            doctor=instance.doctor,
            date=instance.date,
            start_time=instance.start_time
        ).update(is_available=False)
        logger.info(f"Horario bloqueado para cita {instance.appointment_number}")

    elif instance.status in ['cancelled', 'no_show']:
        # Liberar el horario
        TimeSlot.objects.filter(
            doctor=instance.doctor,
            date=instance.date,
            start_time=instance.start_time
        ).update(is_available=True)
        logger.info(f"Horario liberado por {instance.status}")


@receiver(post_save, sender=Appointment)
def send_appointment_notifications(sender, instance, created, **kwargs):
    """
    Enviar notificaciones según el estado de la cita
    """
    from apps.notifications.models import Notification

    if created:
        # Notificar al paciente - Cita creada
        Notification.objects.create(
            recipient=instance.patient,
            notification_type='appointment_confirmed',
            channel='email',
            title=f'Cita agendada - {instance.clinic.name}',
            message=f'Tu cita con Dr. {instance.doctor.user.full_name} ha sido agendada para el {instance.date} a las {instance.start_time}.',
            action_url=f'/appointments/{instance.id}'
        )

        # Notificar al doctor
        Notification.objects.create(
            recipient=instance.doctor.user,
            notification_type='appointment_confirmed',
            channel='in_app',
            title='Nueva cita agendada',
            message=f'Tienes una nueva cita con {instance.patient.full_name} el {instance.date} a las {instance.start_time}.',
            action_url=f'/admin/appointments/{instance.id}'
        )

        logger.info(f"Notificaciones enviadas para cita {instance.appointment_number}")

    elif instance.status == 'confirmed' and hasattr(instance, '_previous_status'):
        if instance._previous_status == 'pending':
            # Cita confirmada
            Notification.objects.create(
                recipient=instance.patient,
                notification_type='appointment_confirmed',
                channel='email',
                title='Tu cita ha sido confirmada',
                message=f'Tu cita con Dr. {instance.doctor.user.full_name} ha sido confirmada.',
                action_url=f'/appointments/{instance.id}'
            )

    elif instance.status == 'cancelled':
        # Notificar cancelación
        cancelled_by_name = instance.cancelled_by.full_name if instance.cancelled_by else 'Sistema'

        Notification.objects.create(
            recipient=instance.patient,
            notification_type='appointment_cancelled',
            channel='email',
            title='Cita cancelada',
            message=f'Tu cita del {instance.date} ha sido cancelada por {cancelled_by_name}.',
        )

        Notification.objects.create(
            recipient=instance.doctor.user,
            notification_type='appointment_cancelled',
            channel='in_app',
            title='Cita cancelada',
            message=f'La cita con {instance.patient.full_name} del {instance.date} ha sido cancelada.',
        )


@receiver(post_save, sender=Appointment)
def schedule_appointment_reminders(sender, instance, created, **kwargs):
    """
    Programar recordatorios de cita (requiere Celery)
    """
    if created and instance.status in ['pending', 'confirmed']:
        try:
            from apps.notifications.tasks import send_appointment_reminder
            from datetime import datetime, timedelta

            # Recordatorio 24 horas antes
            reminder_time_24h = timezone.make_aware(
                datetime.combine(instance.date, instance.start_time) - timedelta(hours=24)
            )

            if reminder_time_24h > timezone.now():
                send_appointment_reminder.apply_async(
                    args=[str(instance.id)],
                    eta=reminder_time_24h
                )
                logger.info(f"Recordatorio 24h programado para cita {instance.appointment_number}")

            # Recordatorio 1 hora antes
            reminder_time_1h = timezone.make_aware(
                datetime.combine(instance.date, instance.start_time) - timedelta(hours=1)
            )

            if reminder_time_1h > timezone.now():
                send_appointment_reminder.apply_async(
                    args=[str(instance.id)],
                    eta=reminder_time_1h
                )
                logger.info(f"Recordatorio 1h programado para cita {instance.appointment_number}")

        except ImportError:
            logger.warning("Celery no configurado, recordatorios no programados")


@receiver(post_save, sender=Appointment)
def request_review_after_completion(sender, instance, **kwargs):
    """
    Solicitar reseña después de completar la cita
    """
    if instance.status == 'completed' and hasattr(instance, '_previous_status'):
        if instance._previous_status != 'completed':
            from apps.notifications.models import Notification

            # Enviar notificación 1 hora después de la cita
            from datetime import timedelta
            review_time = timezone.now() + timedelta(hours=1)

            Notification.objects.create(
                recipient=instance.patient,
                notification_type='review_request',
                channel='email',
                title='¿Cómo fue tu experiencia?',
                message=f'Por favor, cuéntanos cómo fue tu visita con Dr. {instance.doctor.user.full_name}.',
                action_url=f'/reviews/new/{instance.id}',
                scheduled_at=review_time
            )

            logger.info(f"Solicitud de reseña programada para cita {instance.appointment_number}")


@receiver(post_delete, sender=Appointment)
def release_time_slot_on_delete(sender, instance, **kwargs):
    """
    Liberar horario si se elimina la cita
    """
    TimeSlot.objects.filter(
        doctor=instance.doctor,
        date=instance.date,
        start_time=instance.start_time
    ).update(is_available=True)
    logger.info(f"Horario liberado por eliminación de cita {instance.appointment_number}")

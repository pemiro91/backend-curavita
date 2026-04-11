import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

from .models import Notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Notification)
def send_notification_on_create(sender, instance, created, **kwargs):
    """
    Enviar notificación inmediatamente si no está programada
    """
    if created and not instance.scheduled_at:
        send_notification(instance)


def send_notification(notification):
    """
    Enviar notificación según el canal
    """
    if notification.channel == 'email':
        send_email_notification(notification)
    elif notification.channel == 'sms':
        send_sms_notification(notification)
    elif notification.channel == 'push':
        send_push_notification(notification)

    # Marcar como enviada
    notification.status = 'sent'
    notification.save(update_fields=['status'])


def send_email_notification(notification):
    """
    Enviar notificación por email
    """
    try:
        send_mail(
            subject=notification.title,
            message=notification.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.recipient.email],
            fail_silently=True,
        )
        notification.status = 'delivered'
        notification.save(update_fields=['status'])
        logger.info(f"Email enviado a {notification.recipient.email}")
    except Exception as e:
        notification.status = 'failed'
        notification.error_message = str(e)
        notification.save(update_fields=['status', 'error_message'])
        logger.error(f"Error enviando email: {e}")


def send_sms_notification(notification):
    """
    Enviar notificación por SMS (requiere integración con Twilio)
    """
    # Implementar con Twilio u otro servicio
    logger.info(f"SMS notification pendiente de implementación")
    pass


def send_push_notification(notification):
    """
    Enviar notificación push (requiere FCM o similar)
    """
    # Implementar con Firebase Cloud Messaging
    logger.info(f"Push notification pendiente de implementación")
    pass
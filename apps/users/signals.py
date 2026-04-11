import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import User, Address

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_notification_preferences(sender, instance, created, **kwargs):
    """
    Crear preferencias de notificación por defecto cuando se crea un usuario
    """
    if created:
        from apps.notifications.models import NotificationPreference
        NotificationPreference.objects.get_or_create(user=instance)
        logger.info(f"Preferencias de notificación creadas para {instance.email}")


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """
    Enviar email de bienvenida cuando se crea un usuario
    """
    if created and not instance.is_staff:
        try:
            send_mail(
                subject='Bienvenido a Health Hub Connect',
                message=f'''
                Hola {instance.first_name},

                ¡Bienvenido a Health Hub Connect!

                Tu cuenta ha sido creada exitosamente.
                Email: {instance.email}

                Puedes iniciar sesión en: https://yourdomain.com/login

                Saludos,
                El equipo de Health Hub Connect
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.email],
                fail_silently=True,
            )
            logger.info(f"Email de bienvenida enviado a {instance.email}")
        except Exception as e:
            logger.error(f"Error enviando email de bienvenida: {e}")


@receiver(pre_save, sender=User)
def track_user_changes(sender, instance, **kwargs):
    """
    Rastrear cambios en el usuario antes de guardar
    """
    if instance.pk:
        try:
            old_user = User.objects.get(pk=instance.pk)
            instance._old_email = old_user.email
            instance._old_is_active = old_user.is_active
        except User.DoesNotExist:
            pass


@receiver(post_save, sender=User)
def handle_user_status_change(sender, instance, created, **kwargs):
    """
    Manejar cambios de estado del usuario
    """
    if not created and hasattr(instance, '_old_is_active'):
        # Si el usuario fue activado/desactivado
        if instance._old_is_active != instance.is_active:
            if instance.is_active:
                logger.info(f"Usuario {instance.email} activado")
            else:
                logger.info(f"Usuario {instance.email} desactivado")


@receiver(post_save, sender=Address)
def ensure_single_default_address(sender, instance, created, **kwargs):
    """
    Asegurar que solo haya una dirección por defecto por usuario
    """
    if instance.is_default:
        Address.objects.filter(user=instance.user).exclude(pk=instance.pk).update(is_default=False)

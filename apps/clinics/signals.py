import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

from .models import Clinic, Doctor, ClinicImage

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Clinic)
def clinic_status_notification(sender, instance, created, **kwargs):
    """
    Notificar a admins cuando el estado de la clínica cambia
    """
    if not created:
        # Notificar si la clínica fue aprobada
        if instance.status == 'active' and hasattr(instance, '_previous_status'):
            if instance._previous_status == 'pending':
                for admin in instance.admins.all():
                    try:
                        send_mail(
                            subject='Tu clínica ha sido aprobada',
                            message=f'''
                            Hola {admin.first_name},

                            Nos complace informarte que tu clínica "{instance.name}" 
                            ha sido aprobada y ya está activa en nuestra plataforma.

                            Puedes comenzar a recibir citas.

                            Saludos,
                            Equipo Health Hub Connect
                            ''',
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[admin.email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        logger.error(f"Error enviando notificación de aprobación: {e}")


@receiver(pre_save, sender=Clinic)
def store_previous_status(sender, instance, **kwargs):
    """
    Guardar estado anterior para comparar después
    """
    if instance.pk:
        try:
            old_clinic = Clinic.objects.get(pk=instance.pk)
            instance._previous_status = old_clinic.status
        except Clinic.DoesNotExist:
            pass


@receiver(post_save, sender=Doctor)
def doctor_profile_created(sender, instance, created, **kwargs):
    """
    Acciones cuando se crea un perfil de doctor
    """
    if created:
        logger.info(f"Perfil de doctor creado para {instance.user.email}")

        # Notificar al doctor
        try:
            send_mail(
                subject='Tu perfil de médico ha sido creado',
                message=f'''
                Dr. {instance.user.full_name},

                Tu perfil de médico ha sido creado exitosamente en {instance.clinic.name}.

                Especialidad: {instance.specialty.name}

                Puedes comenzar a recibir citas.

                Saludos,
                Equipo Health Hub Connect
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Error notificando creación de doctor: {e}")


@receiver(post_delete, sender=ClinicImage)
def delete_clinic_image_file(sender, instance, **kwargs):
    """
    Eliminar archivo de imagen cuando se borra el registro
    """
    if instance.image:
        try:
            instance.image.delete(save=False)
            logger.info(f"Imagen de clínica eliminada: {instance.image.name}")
        except Exception as e:
            logger.error(f"Error eliminando imagen: {e}")


@receiver(post_save, sender=Doctor)
def update_doctor_rating_on_save(sender, instance, **kwargs):
    """
    Actualizar rating del doctor si cambian las reseñas
    (Este signal se complementa con el de reviews)
    """
    pass  # La lógica principal está en reviews/signals.py

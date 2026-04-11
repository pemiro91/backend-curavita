import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg

from .models import Review, ReviewHelpful

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Review)
def update_entity_rating_on_save(sender, instance, created, **kwargs):
    """
    Actualizar el rating promedio de clínica o doctor cuando se guarda una reseña
    """
    if instance.status == 'approved':
        if instance.clinic:
            update_clinic_rating(instance.clinic)

        if instance.doctor:
            update_doctor_rating(instance.doctor)

        logger.info(f"Rating actualizado para review {instance.id}")


@receiver(post_delete, sender=Review)
def update_entity_rating_on_delete(sender, instance, **kwargs):
    """
    Actualizar rating cuando se elimina una reseña
    """
    if instance.clinic:
        update_clinic_rating(instance.clinic)

    if instance.doctor:
        update_doctor_rating(instance.doctor)

    logger.info(f"Rating actualizado tras eliminar review {instance.id}")


def update_clinic_rating(clinic):
    """
    Calcular y actualizar el rating promedio de una clínica
    """
    from .models import Review

    reviews = Review.objects.filter(clinic=clinic, status='approved')

    if reviews.exists():
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
        clinic.rating = round(avg_rating, 1)
        clinic.review_count = reviews.count()
    else:
        clinic.rating = 0.0
        clinic.review_count = 0

    clinic.save(update_fields=['rating', 'review_count'])
    logger.info(f"Rating de clínica {clinic.name}: {clinic.rating}")


def update_doctor_rating(doctor):
    """
    Calcular y actualizar el rating promedio de un doctor
    """
    from .models import Review

    reviews = Review.objects.filter(doctor=doctor, status='approved')

    if reviews.exists():
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
        doctor.rating = round(avg_rating, 1)
        doctor.review_count = reviews.count()
    else:
        doctor.rating = 0.0
        doctor.review_count = 0

    doctor.save(update_fields=['rating', 'review_count'])
    logger.info(f"Rating de Dr. {doctor.user.full_name}: {doctor.rating}")


@receiver(post_save, sender=Review)
def notify_entity_about_review(sender, instance, created, **kwargs):
    """
    Notificar a clínica/doctor sobre nueva reseña
    """
    if created and instance.status == 'approved':
        from apps.notifications.models import Notification

        if instance.doctor:
            Notification.objects.create(
                recipient=instance.doctor.user,
                notification_type='system',
                channel='in_app',
                title='Nueva reseña recibida',
                message=f'Has recibido una nueva reseña de {instance.patient.full_name}: {instance.rating} estrellas.',
                action_url=f'/reviews/{instance.id}'
            )

        if instance.clinic:
            for admin in instance.clinic.admins.all():
                Notification.objects.create(
                    recipient=admin,
                    notification_type='system',
                    channel='in_app',
                    title='Nueva reseña en tu clínica',
                    message=f'Tu clínica recibió una nueva reseña: {instance.rating} estrellas.',
                    action_url=f'/reviews/{instance.id}'
                )


@receiver(post_save, sender=ReviewHelpful)
def update_helpful_count(sender, instance, created, **kwargs):
    """
    Actualizar contador de 'útil' en la reseña
    """
    if created:
        review = instance.review
        review.helpful_count = ReviewHelpful.objects.filter(review=review).count()
        review.save(update_fields=['helpful_count'])
        logger.info(f"Contador de útil actualizado para review {review.id}: {review.helpful_count}")


@receiver(post_delete, sender=ReviewHelpful)
def decrement_helpful_count(sender, instance, **kwargs):
    """
    Decrementar contador cuando se elimina un voto
    """
    review = instance.review
    review.helpful_count = max(0, ReviewHelpful.objects.filter(review=review).count())
    review.save(update_fields=['helpful_count'])
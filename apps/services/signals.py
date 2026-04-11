import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Specialty

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Specialty)
def create_slug_for_specialty(sender, instance, created, **kwargs):
    """
    Crear slug automáticamente si no existe
    """
    if created and not instance.slug:
        from django.utils.text import slugify
        instance.slug = slugify(instance.name)
        instance.save(update_fields=['slug'])
        logger.info(f"Slug creado para especialidad: {instance.slug}")

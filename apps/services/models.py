import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class Specialty(models.Model):
    """Especialidad médica"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(_('name'), max_length=100, unique=True)
    slug = models.SlugField(_('slug'), unique=True, max_length=100)
    description = models.TextField(_('description'), blank=True)

    icon = models.CharField(
        _('icon'),
        max_length=50,
        blank=True,
        help_text=_('Lucide icon name (e.g., Stethoscope, Heart)')
    )

    color = models.CharField(
        _('color'),
        max_length=7,
        default='#3B82F6',
        help_text=_('Hex color code')
    )

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('specialty')
        verbose_name_plural = _('specialties')
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Service(models.Model):
    """Servicio ofrecido por una clínica"""

    class ServiceType(models.TextChoices):
        CONSULTATION = 'consultation', _('Consulta')
        EXAM = 'exam', _('Examen')
        PROCEDURE = 'procedure', _('Procedimiento')
        VACCINATION = 'vaccination', _('Vacunación')
        THERAPY = 'therapy', _('Terapia')
        OTHER = 'other', _('Otro')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        'clinics.Clinic',
        on_delete=models.CASCADE,
        related_name='services'
    )
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.PROTECT,
        related_name='services',
        verbose_name=_('specialty')
    )

    name = models.CharField(_('name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    service_type = models.CharField(
        _('service type'),
        max_length=20,
        choices=ServiceType.choices,
        default=ServiceType.CONSULTATION
    )

    # Precio y duración
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField(_('duration (minutes)'), default=30)

    # Requisitos
    requires_preparation = models.BooleanField(_('requires preparation'), default=False)
    preparation_instructions = models.TextField(_('preparation instructions'), blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    slug = models.SlugField(unique=True, max_length=200, blank=True)

    icon = models.CharField(
        _('icon'),
        max_length=50,
        blank=True,
        default='stethoscope',
        help_text=_('Lucide icon name (e.g., Stethoscope, Heart)')
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            import itertools
            base_slug = slugify(self.name)
            slug = base_slug
            for i in itertools.count(1):
                if not Service.objects.filter(slug=slug).exists():
                    break
                slug = f"{base_slug}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('service')
        verbose_name_plural = _('services')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.clinic.name}"

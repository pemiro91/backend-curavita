import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from apps.users.models import User


class Clinic(models.Model):
    """Modelo de Clínica"""

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pendiente')
        ACTIVE = 'active', _('Activa')
        SUSPENDED = 'suspended', _('Suspendida')
        INACTIVE = 'inactive', _('Inactiva')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Información básica
    name = models.CharField(_('name'), max_length=200)
    slug = models.SlugField(_('slug'), unique=True, max_length=200)
    description = models.TextField(_('description'), blank=True)

    # Contacto
    email = models.EmailField(_('email'))
    phone = models.CharField(_('phone'), max_length=20)
    website = models.URLField(_('website'), blank=True)

    # Dirección
    street = models.CharField(_('street'), max_length=255)
    number = models.CharField(_('number'), max_length=20)
    complement = models.CharField(_('complement'), max_length=100, blank=True)
    neighborhood = models.CharField(_('neighborhood'), max_length=100)
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state'), max_length=100)
    zip_code = models.CharField(_('zip code'), max_length=20)

    # Geolocalización
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Imágenes
    logo = models.ImageField(_('logo'), upload_to='clinics/logos/', blank=True, null=True)
    cover_image = models.ImageField(_('cover image'), upload_to='clinics/covers/', blank=True, null=True)

    # Administradores
    admins = models.ManyToManyField(
        User,
        related_name='managed_clinics',
        limit_choices_to={'user_type__in': ['clinic_admin', 'super_admin']}
    )

    # Configuración
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # Horario de atención
    opening_time = models.TimeField(_('opening time'), default='08:00')
    closing_time = models.TimeField(_('closing time'), default='18:00')

    # Configuración de citas
    appointment_duration = models.PositiveIntegerField(
        _('appointment duration (minutes)'),
        default=30
    )
    max_appointments_per_day = models.PositiveIntegerField(
        _('max appointments per day'),
        default=50
    )
    allow_online_booking = models.BooleanField(_('allow online booking'), default=True)

    # Metadatos
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0.0)
    review_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('clinic')
        verbose_name_plural = _('clinics')
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def update_rating(self):
        """Actualizar rating promedio"""
        from apps.reviews.models import Review
        reviews = Review.objects.filter(clinic=self, status='approved')
        if reviews.exists():
            self.rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
            self.review_count = reviews.count()
            self.save(update_fields=['rating', 'review_count'])

    @property
    def is_active(self):
        return self.status == 'active'


class Doctor(models.Model):
    """Médico de la clínica"""

    class Status(models.TextChoices):
        ACTIVE = 'active', _('Activo')
        INACTIVE = 'inactive', _('Inactivo')
        ON_VACATION = 'on_vacation', _('De Vacaciones')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='doctor_profile',
        limit_choices_to={'user_type': 'doctor'}
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='doctors'
    )

    # Información profesional
    license_number = models.CharField(_('license number'), max_length=50)
    specialty = models.ForeignKey(
        'services.Specialty',
        on_delete=models.PROTECT,
        related_name='doctors',
        verbose_name=_('specialty')
    )
    secondary_specialties = models.ManyToManyField(
        'services.Specialty',
        related_name='secondary_doctors',
        blank=True,
        verbose_name=_('secondary specialties')
    )

    # Biografía
    bio = models.TextField(_('biography'), blank=True)
    education = models.TextField(_('education'), blank=True)
    experience_years = models.PositiveIntegerField(_('years of experience'), default=0)

    # Horario de atención (JSON para flexibilidad)
    schedule = models.JSONField(
        _('schedule'),
        default=dict,
        help_text=_('Format: {"monday": [{"start": "09:00", "end": "17:00"}], ...}')
    )

    # Configuración
    consultation_fee = models.DecimalField(
        _('consultation fee'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    # Metadatos
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0.0)
    review_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('doctor')
        verbose_name_plural = _('doctors')
        ordering = ['-created_at']

    def __str__(self):
        return f"Dr. {self.user.full_name} - {self.specialty.name}"


class ClinicImage(models.Model):
    """Imágenes adicionales de la clínica"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='clinics/gallery/')
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

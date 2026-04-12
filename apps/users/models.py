# apps/users/models.py
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Modelo de usuario personalizado"""

    class UserType(models.TextChoices):
        PATIENT = 'patient', _('Paciente')
        DOCTOR = 'doctor', _('Médico')
        CLINIC_ADMIN = 'clinic_admin', _('Administrador de Clínica')
        SUPER_ADMIN = 'super_admin', _('Super Administrador')

    class Gender(models.TextChoices):
        MALE = 'male', _('Masculino')
        FEMALE = 'female', _('Femenino')
        OTHER = 'other', _('Otro')
        PREFER_NOT_TO_SAY = 'prefer_not_to_say', _('Prefiero no decir')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=150)
    last_name = models.CharField(_('last name'), max_length=150)

    # Campos adicionales
    phone = PhoneNumberField(_('phone number'), blank=True, null=True)
    document_number = models.CharField(_('document number'), max_length=20, blank=True)
    date_of_birth = models.DateField(_('date of birth'), null=True, blank=True)
    gender = models.CharField(_('gender'), max_length=20, choices=Gender.choices, blank=True)
    avatar = models.ImageField(_('avatar'), upload_to='avatars/', blank=True, null=True)

    # Tipo de usuario
    user_type = models.CharField(
        _('user type'),
        max_length=20,
        choices=UserType.choices,
        default=UserType.PATIENT
    )

    # Estados
    is_staff = models.BooleanField(
        default=False,
        help_text='Designa si el usuario puede entrar al sitio de administración.',
        verbose_name='Es staff'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Designa si el usuario debe ser tratado como activo.',
        verbose_name='Está activo'
    )
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)

    # Preferencias
    preferred_language = models.CharField(
        max_length=10,
        choices=[('pt', 'Português'), ('es', 'Español'), ('en', 'English'), ('fr', 'Français')],
        default='pt'
    )
    receive_notifications = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - (
                    (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None


class Address(models.Model):
    """Dirección del usuario"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')

    street = models.CharField(_('street'), max_length=255)
    number = models.CharField(_('number'), max_length=20)
    complement = models.CharField(_('complement'), max_length=100, blank=True)
    neighborhood = models.CharField(_('neighborhood'), max_length=100)
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state'), max_length=100)
    zip_code = models.CharField(_('zip code'), max_length=20)
    country = models.CharField(_('country'), max_length=100, default='Brasil')

    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('address')
        verbose_name_plural = _('addresses')

    def __str__(self):
        return f"{self.street}, {self.number} - {self.city}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Desmarcar otras direcciones como default
            Address.objects.filter(user=self.user).update(is_default=False)
        super().save(*args, **kwargs)

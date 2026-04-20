import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

from apps.users.models import User
from apps.clinics.models import Clinic, Doctor
from apps.appointments.models import Appointment


class Review(models.Model):
    """Reseña de clínica o médico"""

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pendiente')
        APPROVED = 'approved', _('Aprobada')
        REJECTED = 'rejected', _('Rechazada')

    class ReviewType(models.TextChoices):
        CLINIC = 'clinic', _('Clínica')
        DOCTOR = 'doctor', _('Médico')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Quién hace la reseña
    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews',
        limit_choices_to={'user_type': 'patient'}
    )

    # Tipo de reseña
    review_type = models.CharField(max_length=10, choices=ReviewType.choices)

    # Relaciones (una debe estar presente según el tipo)
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='reviews',
        null=True,
        blank=True
    )
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='reviews',
        null=True,
        blank=True
    )

    # Cita asociada (opcional, para verificar que usó el servicio)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review'
    )

    # Contenido de la reseña
    rating = models.PositiveSmallIntegerField(
        _('rating'),
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(_('title'), max_length=200, blank=True)
    comment = models.TextField(_('comment'))

    # Moderación
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    moderated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_reviews'
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_notes = models.TextField(blank=True)

    # Respuesta del admin/clínica
    response = models.TextField(_('response'), blank=True)
    response_date = models.DateTimeField(_('response date'), null=True, blank=True)
    responded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review_responses'
    )

    # Utilidad
    helpful_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('review')
        verbose_name_plural = _('reviews')
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['patient', 'appointment'],
                name='unique_review_per_appointment',
                condition=models.Q(appointment__isnull=False)
            ),
        ]

    def __str__(self):
        return f"{self.patient.full_name} - {self.rating}★"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Actualizar rating del médico o clínica
        if self.doctor and self.status == 'approved':
            self.doctor.update_rating()
        if self.clinic and self.status == 'approved':
            self.clinic.update_rating()


class ReviewHelpful(models.Model):
    """Registro de usuarios que marcaron una reseña como útil"""
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['review', 'user']

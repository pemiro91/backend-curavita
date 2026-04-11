import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.users.models import User


class Notification(models.Model):
    """Notificaciones para usuarios"""

    class NotificationType(models.TextChoices):
        APPOINTMENT_CONFIRMED = 'appointment_confirmed', _('Cita Confirmada')
        APPOINTMENT_REMINDER = 'appointment_reminder', _('Recordatorio de Cita')
        APPOINTMENT_CANCELLED = 'appointment_cancelled', _('Cita Cancelada')
        APPOINTMENT_COMPLETED = 'appointment_completed', _('Cita Completada')
        REVIEW_REQUEST = 'review_request', _('Solicitud de Reseña')
        SYSTEM = 'system', _('Sistema')
        PROMOTION = 'promotion', _('Promoción')

    class Channel(models.TextChoices):
        EMAIL = 'email', _('Email')
        SMS = 'sms', _('SMS')
        PUSH = 'push', _('Push Notification')
        IN_APP = 'in_app', _('In-App')

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pendiente')
        SENT = 'sent', _('Enviada')
        DELIVERED = 'delivered', _('Entregada')
        READ = 'read', _('Leída')
        FAILED = 'failed', _('Fallida')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )
    channel = models.CharField(max_length=10, choices=Channel.choices)

    # Contenido
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Datos adicionales

    # Enlaces
    action_url = models.URLField(blank=True)
    action_text = models.CharField(max_length=50, blank=True)

    # Estado
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # Tiempos
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Error
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('notification')
        verbose_name_plural = _('notifications')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.email} - {self.title}"

    def mark_as_read(self):
        from django.utils import timezone
        self.status = 'read'
        self.read_at = timezone.now()
        self.save(update_fields=['status', 'read_at'])


class NotificationPreference(models.Model):
    """Preferencias de notificación por usuario"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )

    # Canales habilitados
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=True)

    # Tipos de notificación
    appointment_reminders = models.BooleanField(default=True)
    appointment_updates = models.BooleanField(default=True)
    promotional_emails = models.BooleanField(default=False)

    # Horario de notificación
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification, NotificationPreference

User = get_user_model()


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer para notificaciones.
    """
    recipient_name = serializers.CharField(source='recipient.get_full_name', read_only=True)
    recipient_email = serializers.CharField(source='recipient.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'recipient_name', 'recipient_email',
            'notification_type', 'notification_type_display',
            'channel', 'channel_display',
            'title', 'message', 'status', 'status_display',
            'is_read', 'read_at', 'sent_at', 'delivered_at',
            'created_at', 'data'
        ]
        read_only_fields = [
            'id', 'recipient', 'sent_at', 'delivered_at',
            'created_at'
        ]

    def get_is_read(self, obj):
        """Retorna True si la notificación fue leída."""
        return obj.status == 'read'


class NotificationCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear notificaciones (uso interno/admin).
    """
    recipient_email = serializers.EmailField(write_only=True, required=True)

    class Meta:
        model = Notification
        fields = [
            'recipient_email', 'notification_type', 'channel',
            'title', 'message', 'data'
        ]

    def validate_recipient_email(self, value):
        """Validar que el usuario existe."""
        try:
            user = User.objects.get(email=value.lower().strip())
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError("Usuario no encontrado.")

    def create(self, validated_data):
        recipient = validated_data.pop('recipient_email')
        validated_data['recipient'] = recipient
        validated_data['status'] = 'pending'
        return super().create(validated_data)


class NotificationUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar notificación (solo status generalmente).
    """

    class Meta:
        model = Notification
        fields = ['status', 'read_at']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """
    Serializer para preferencias de notificación del usuario.
    """
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'user_email',
            # Canales
            'email_enabled', 'push_enabled', 'sms_enabled',
            # Tipos de notificación
            # 'notify_appointment_reminders',
            # 'notify_appointment_changes',
            # 'notify_promotions',
            # 'notify_system_updates',
            # 'notify_new_reviews',
            # 'notify_chat_messages',
            # Horario
            'quiet_hours_start', 'quiet_hours_end',
            # 'timezone',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'user_email', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Validar horario de no molestar."""
        quiet_start = attrs.get('quiet_hours_start', self.instance.quiet_hours_start if self.instance else None)
        quiet_end = attrs.get('quiet_hours_end', self.instance.quiet_hours_end if self.instance else None)

        if quiet_start and quiet_end and quiet_start == quiet_end:
            raise serializers.ValidationError(
                {"quiet_hours_end": "La hora de inicio y fin no pueden ser iguales."}
            )

        return attrs


class NotificationBulkActionSerializer(serializers.Serializer):
    """
    Serializer para acciones masivas sobre notificaciones.
    """
    notification_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True
    )
    action = serializers.ChoiceField(
        choices=[
            ('mark_as_read', 'Marcar como leída'),
            ('mark_as_unread', 'Marcar como no leída'),
            ('delete', 'Eliminar'),
        ],
        required=True
    )

    def validate_notification_ids(self, value):
        """Validar que las notificaciones existen y pertenecen al usuario."""
        if not value:
            raise serializers.ValidationError("Debe proporcionar al menos un ID.")
        return value


class NotificationStatsSerializer(serializers.Serializer):
    """
    Serializer para estadísticas de notificaciones.
    """
    total_notifications = serializers.IntegerField()
    unread_count = serializers.IntegerField()
    read_count = serializers.IntegerField()
    by_type = serializers.DictField(child=serializers.IntegerField())
    by_channel = serializers.DictField(child=serializers.IntegerField())
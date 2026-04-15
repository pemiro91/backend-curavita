import logging
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import Notification, NotificationPreference
from .serializers import (
    NotificationSerializer,
    NotificationPreferenceSerializer,
    NotificationCreateSerializer,
)
from ..users.permissions import IsSuperAdmin

logger = logging.getLogger(__name__)

@extend_schema(tags=['Notificaciones'])
class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de notificaciones.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'notification_type']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationCreateSerializer  # ← AHORA SÍ SE USA
        return NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def get_permissions(self):
        # Solo super_admin puede crear notificaciones manualmente
        if self.action == 'create':
            return [IsAuthenticated(), IsSuperAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        """El recipient se asigna desde el serializer, no del request.user"""
        serializer.save()

@extend_schema(tags=['Notificaciones'])
class MyNotificationsView(generics.ListAPIView):
    """
    Vista para listar notificaciones del usuario.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')

@extend_schema(tags=['Notificaciones'])
class MarkNotificationAsReadView(generics.GenericAPIView):
    """
    Vista para marcar notificación como leída.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = Notification.objects.get(id=pk, recipient=request.user)
        notification.mark_as_read()
        return Response({'message': 'Notificación marcada como leída.'})

@extend_schema(tags=['Notificaciones'])
class MarkAllNotificationsAsReadView(generics.GenericAPIView):
    """
    Vista para marcar todas las notificaciones como leídas.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(
            recipient=request.user,
            status__in=['sent', 'delivered']
        ).update(status='read', read_at=timezone.now())

        return Response({'message': 'Todas las notificaciones marcadas como leídas.'})

@extend_schema(tags=['Notificaciones'])
class NotificationPreferencesView(generics.RetrieveUpdateAPIView):
    """
    Vista para gestionar preferencias de notificación.
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        preference, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return preference

@extend_schema(tags=['Notificaciones'])
class UnreadNotificationsCountView(generics.GenericAPIView):
    """
    Vista para obtener contador de notificaciones no leídas.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user,
            status__in=['sent', 'delivered']
        ).count()

        return Response({'unread_count': count})

@extend_schema(tags=['Notificaciones'])
class DeleteNotificationView(generics.DestroyAPIView):
    """
    Vista para eliminar una notificación.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

@extend_schema(tags=['Notificaciones'])
class TestNotificationView(generics.GenericAPIView):
    """
    Vista para enviar notificación de prueba.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        notification = Notification.objects.create(
            recipient=request.user,
            notification_type='system',
            channel='email',
            title='Notificación de prueba',
            message='Esta es una notificación de prueba.',
            status='pending'
        )

        return Response({
            'message': 'Notificación de prueba creada.',
            'notification_id': str(notification.id)
        })

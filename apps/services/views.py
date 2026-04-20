import logging

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Specialty, Service
from .permissions import IsClinicAdminOrReadOnly
from .serializers import (
    SpecialtySerializer,
    ServiceSerializer,
    ServiceDetailSerializer,
    ServiceCreateSerializer,
    ServiceUpdateSerializer
)

logger = logging.getLogger(__name__)


@extend_schema(tags=['Servicios'])
class SpecialtyViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de especialidades médicas.
    """
    queryset = Specialty.objects.filter(is_active=True)
    serializer_class = SpecialtySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'order']
    lookup_field = 'slug'

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]  # Solo admin puede modificar


@extend_schema(tags=['Servicios'])
class SpecialtyListView(generics.ListAPIView):
    """
    Vista para listar especialidades (público).
    """
    queryset = Specialty.objects.filter(is_active=True)
    serializer_class = SpecialtySerializer
    permission_classes = [AllowAny]


@extend_schema(tags=['Servicios'])
class ServiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de servicios.
    """
    queryset = Service.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['clinic', 'specialty', 'service_type']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'duration_minutes']

    def get_serializer_class(self):
        if self.action == 'create':
            return ServiceCreateSerializer
        elif self.action == 'retrieve':
            return ServiceDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return ServiceUpdateSerializer
        return ServiceSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated(), IsClinicAdminOrReadOnly()]

    def get_queryset(self):
        """Filtrar según el usuario y parámetros"""
        queryset = super().get_queryset()

        # Si NO es admin y NO pide ver todos, filtrar solo activos
        user = self.request.user
        show_all = self.request.query_params.get('show_all') == 'true'

        if not user.is_authenticated or not hasattr(user, 'user_type'):
            # Usuario anónimo: solo activos
            return queryset.filter(is_active=True)

        if user.user_type not in ['clinic_admin', 'super_admin'] and not show_all:
            # Cliente normal: solo activos
            return queryset.filter(is_active=True)

        # Admin o show_all=true: retornar todo (filtrable por is_active si se desea)
        return queryset


@extend_schema(tags=['Servicios'])
class ServiceByClinicView(generics.ListAPIView):
    """
    Vista para listar servicios de una clínica específica.
    """
    serializer_class = ServiceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        clinic_id = self.kwargs['clinic_id']
        return Service.objects.filter(
            clinic_id=clinic_id,
            is_active=True
        ).select_related('specialty')


# apps/services/views.py - Agregar si falta
@extend_schema(tags=['Servicios'])
class ServiceBySpecialtyView(generics.ListAPIView):
    """Servicios por especialidad"""
    serializer_class = ServiceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        specialty_id = self.kwargs.get('specialty_id')
        return Service.objects.filter(specialty_id=specialty_id, is_active=True)

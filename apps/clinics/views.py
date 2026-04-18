import logging

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from geopy.distance import geodesic
from rest_framework import filters
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import Clinic, Doctor, ClinicImage
from .permissions import IsClinicAdminOrReadOnly, IsClinicAdmin
from .serializers import (
    ClinicListSerializer,
    ClinicDetailSerializer,
    ClinicCreateSerializer,
    DoctorListSerializer,
    DoctorDetailSerializer,
    DoctorCreateSerializer,
    ClinicImageSerializer,
)

logger = logging.getLogger(__name__)

@extend_schema(tags=['Clínicas'])
class ClinicViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de clínicas.
    """
    queryset = Clinic.objects.filter(status__in=['active', 'pending'])
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'state', 'status']
    search_fields = ['name', 'description', 'city', 'neighborhood']
    ordering_fields = ['name', 'rating', 'created_at', 'opening_time']
    ordering = ['-rating', 'name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ClinicListSerializer
        elif self.action == 'create':
            return ClinicCreateSerializer
        return ClinicDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'nearby', 'search']:
            return [AllowAny()]
        return [IsAuthenticated(), IsClinicAdminOrReadOnly()]

    def perform_create(self, serializer):
        clinic = serializer.save()
        clinic.admins.add(self.request.user)
        clinic.status = 'pending'
        clinic.save()

    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Buscar clínicas cercanas por geolocalización"""
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = float(request.query_params.get('radius', 10))  # km

        if not lat or not lng:
            return Response(
                {'error': 'Se requieren latitud y longitud.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_location = (float(lat), float(lng))
        clinics = self.get_queryset()

        nearby_clinics = []
        for clinic in clinics:
            if clinic.latitude and clinic.longitude:
                clinic_location = (clinic.latitude, clinic.longitude)
                distance = geodesic(user_location, clinic_location).kilometers
                if distance <= radius:
                    clinic_data = ClinicListSerializer(clinic).data
                    clinic_data['distance'] = round(distance, 2)
                    nearby_clinics.append(clinic_data)

        nearby_clinics.sort(key=lambda x: x['distance'])
        return Response(nearby_clinics)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Búsqueda avanzada de clínicas"""
        query = request.query_params.get('q', '')
        specialty = request.query_params.get('specialty')
        city = request.query_params.get('city')

        clinics = self.get_queryset()

        if query:
            clinics = clinics.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(services__name__icontains=query)
            ).distinct()

        if specialty:
            clinics = clinics.filter(
                doctors__specialty__slug=specialty
            ).distinct()

        if city:
            clinics = clinics.filter(city__iexact=city)

        page = self.paginate_queryset(clinics)
        if page is not None:
            serializer = ClinicListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = ClinicListSerializer(clinics, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def doctors(self, request, pk=None):
        """Obtener médicos de una clínica"""
        clinic = self.get_object()
        doctors = clinic.doctors.filter(status='active')
        serializer = DoctorListSerializer(doctors, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsClinicAdmin])
    def approve(self, request, pk=None):
        """Aprobar clínica (solo super admin)"""
        if request.user.user_type != 'super_admin':
            raise PermissionDenied('Solo super admin puede aprobar clínicas.')

        clinic = self.get_object()
        clinic.status = 'active'
        clinic.save()
        return Response({'message': 'Clínica aprobada correctamente.'})

    def get_parser_classes(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [MultiPartParser, FormParser, JSONParser]
        return [JSONParser]

@extend_schema(tags=['Clínicas'])
class DoctorViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de médicos.
    """
    queryset = Doctor.objects.filter(status='active')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['clinic', 'specialty', 'clinic__city']
    search_fields = ['user__first_name', 'user__last_name', 'bio']

    def get_serializer_class(self):
        if self.action == 'list':
            return DoctorListSerializer
        elif self.action == 'create':
            return DoctorCreateSerializer
        return DoctorDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'available_slots', 'schedule']:
            return [AllowAny()]
        return [IsAuthenticated(), IsClinicAdmin()]

    @action(detail=True, methods=['get'])
    def available_slots(self, request, pk=None):
        """Obtener horarios disponibles de un médico"""
        from apps.appointments.models import TimeSlot
        from apps.appointments.serializers import TimeSlotSerializer

        doctor = self.get_object()
        date = request.query_params.get('date')

        if not date:
            return Response(
                {'error': 'Se requiere el parámetro date (YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        slots = TimeSlot.objects.filter(
            doctor=doctor,
            date=date,
            is_available=True,
            is_blocked=False
        ).order_by('start_time')

        serializer = TimeSlotSerializer(slots, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        """Obtener horario semanal del médico"""
        doctor = self.get_object()
        return Response(doctor.schedule)

    @action(detail=True, methods=['put'], permission_classes=[IsAuthenticated])
    def update_schedule(self, request, pk=None):
        """Actualizar horario del médico"""
        doctor = self.get_object()

        if request.user != doctor.user and request.user not in doctor.clinic.admins.all():
            raise PermissionDenied('No tienes permiso para editar este horario.')

        doctor.schedule = request.data.get('schedule', doctor.schedule)
        doctor.save()
        return Response({'message': 'Horario actualizado correctamente.'})

@extend_schema(tags=['Clínicas'])
class ClinicImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de imágenes de clínicas.
    """
    serializer_class = ClinicImageSerializer
    permission_classes = [IsAuthenticated, IsClinicAdmin]

    def get_queryset(self):
        clinic_id = self.kwargs.get('clinic_pk')
        return ClinicImage.objects.filter(clinic_id=clinic_id)

    def perform_create(self, serializer):
        clinic_id = self.kwargs.get('clinic_pk')
        clinic = Clinic.objects.get(id=clinic_id)
        serializer.save(clinic=clinic)

@extend_schema(tags=['Clínicas'])
class NearbyClinicsView(generics.ListAPIView):
    """
    Vista para buscar clínicas cercanas.
    """
    serializer_class = ClinicListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Clinic.objects.filter(status='active')

    def list(self, request, *args, **kwargs):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        radius = float(request.query_params.get('radius', 10))

        if not lat or not lng:
            return Response(
                {'error': 'Se requieren latitud y longitud.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Implementar búsqueda por distancia
        clinics = self.get_queryset()[:50]
        serializer = self.get_serializer(clinics, many=True)
        return Response(serializer.data)

@extend_schema(tags=['Clínicas'])
class ClinicSearchView(generics.ListAPIView):
    """
    Vista para búsqueda de clínicas.
    """
    serializer_class = ClinicListSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'description', 'city']
    filterset_fields = ['city', 'state']

    def get_queryset(self):
        return Clinic.objects.filter(status='active')

@extend_schema(tags=['Clínicas'])
class DoctorScheduleView(generics.RetrieveAPIView):
    """
    Vista para obtener horario de un médico.
    """
    queryset = Doctor.objects.all()
    permission_classes = [AllowAny]

    def retrieve(self, request, *args, **kwargs):
        doctor = self.get_object()
        return Response({
            'doctor_id': doctor.id,
            'schedule': doctor.schedule,
            'appointment_duration': doctor.clinic.appointment_duration
        })

@extend_schema(tags=['Clínicas'])
class AvailableSlotsView(generics.GenericAPIView):
    """
    Vista para consultar horarios disponibles.
    """
    permission_classes = [AllowAny]

    def get(self, request, pk=None):
        from apps.appointments.models import TimeSlot
        from apps.appointments.serializers import TimeSlotSerializer

        doctor = Doctor.objects.get(id=pk)
        date = request.query_params.get('date')

        if not date:
            return Response(
                {'error': 'Se requiere el parámetro date.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        slots = TimeSlot.objects.filter(
            doctor=doctor,
            date=date,
            is_available=True,
            is_blocked=False
        ).order_by('start_time')

        serializer = TimeSlotSerializer(slots, many=True)
        return Response(serializer.data)

@extend_schema(tags=['Clínicas'])
class ClinicStatsView(generics.GenericAPIView):
    """
    Vista para estadísticas de clínica/doctor.
    """
    permission_classes = [IsAuthenticated, IsClinicAdmin]

    def get(self, request, pk=None):
        from apps.appointments.models import Appointment

        doctor = Doctor.objects.get(id=pk)

        # Estadísticas
        total_appointments = Appointment.objects.filter(doctor=doctor).count()
        completed_appointments = Appointment.objects.filter(
            doctor=doctor, status='completed'
        ).count()
        cancelled_appointments = Appointment.objects.filter(
            doctor=doctor, status='cancelled'
        ).count()

        return Response({
            'doctor_id': doctor.id,
            'total_appointments': total_appointments,
            'completed_appointments': completed_appointments,
            'cancelled_appointments': cancelled_appointments,
            'completion_rate': round(
                completed_appointments / total_appointments * 100, 2
            ) if total_appointments > 0 else 0,
            'rating': doctor.rating,
            'review_count': doctor.review_count,
        })

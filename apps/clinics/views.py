import logging

from django.core.mail import send_mail
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from geopy.distance import geodesic
from rest_framework import filters
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from backend_curavita import settings

from apps.users.serializers import UserSerializer
from apps.users.models import User

from .models import Clinic, Doctor, ClinicImage
from .permissions import IsClinicAdminOrReadOnly, IsClinicAdmin
from .serializers import (
    ClinicListSerializer, ClinicDetailSerializer, ClinicCreateSerializer,
    DoctorListSerializer, DoctorDetailSerializer, DoctorCreateSerializer,
    ClinicImageSerializer, DoctorUpdateSerializer, ClinicRegisterSerializer,
    ClinicUpdateSerializer, DoctorRegistrationSerializer, ClinicStatsSerializer,
    ClinicRejectSerializer
)
from ..appointments.serializers import TimeSlotSerializer
from ..appointments.utils import generate_slots_from_schedule

logger = logging.getLogger(__name__)


@extend_schema(tags=['Clínicas'])
class ClinicViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de clínicas.
    """
    queryset = Clinic.objects.filter(status__in=['active', 'pending', 'suspended', 'inactive'])
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'state', 'status', 'services', 'status']
    lookup_field = 'slug'
    search_fields = ['name', 'description', 'city', 'neighborhood']
    ordering_fields = ['name', 'rating', 'created_at', 'opening_time']
    ordering = ['-rating', 'name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ClinicListSerializer
        elif self.action == 'create':
            return ClinicCreateSerializer
        elif self.action == 'retrieve':
            return ClinicDetailSerializer
        return ClinicDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'nearby', 'search']:
            return [AllowAny()]
        return [IsAuthenticated(), IsClinicAdminOrReadOnly()]

    def get_queryset(self):
        """Sobrescribir para filtrar por servicio si se envía el parámetro"""
        queryset = super().get_queryset()
        user = self.request.user

        # Filtro por servicio específico
        if self.action == 'list':
            if not user.is_authenticated:
                return queryset.filter(status='active')
            if not hasattr(user, 'user_type') or user.user_type not in ['clinic_admin', 'super_admin']:
                return queryset.filter(status='active')

        return queryset

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

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        if request.user.user_type != 'super_admin':
            raise PermissionDenied('Solo super admin puede aprobar clínicas.')

        clinic = self.get_object()
        clinic.status = 'active'
        clinic.approved_at = timezone.now()
        clinic.approved_by = request.user

        # Crear clinic_admin si no hay admins o applicant_email existe
        if clinic.applicant_email and not clinic.admins.exists():
            from apps.users.models import User
            temp_password = User.objects.make_random_password()
            admin_user = User.objects.create_user(
                email=clinic.applicant_email,
                first_name='Admin',
                last_name=clinic.name[:30],
                password=temp_password,
                user_type='clinic_admin',
                is_verified=True
            )
            clinic.admins.add(admin_user)
            # Enviar email con credenciales temporales
            send_mail(
                subject='Tu clínica ha sido aprobada',
                message=f'Hola,\n\nTu clínica {clinic.name} ha sido aprobada. Credenciales:\nEmail: {admin_user.email}\nPassword: {temp_password}\n\nPor favor cambia la contraseña al iniciar sesión.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[clinic.applicant_email],
                fail_silently=True,
            )
        clinic.save(update_fields=['status', 'approved_at', 'approved_by'])
        return Response({'message': 'Clínica aprobada correctamente.'})

    def get_parser_classes(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [MultiPartParser, FormParser, JSONParser]
        return [JSONParser]

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def change_status(self, request, slug=None):
        """Cambiar estado de la clínica (solo super admin)"""
        if request.user.user_type != 'super_admin':
            raise PermissionDenied('Solo super admin puede cambiar el estado.')

        clinic = self.get_object()
        new_status = request.data.get('status')

        valid_statuses = ['pending', 'active', 'suspended', 'inactive']
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Estado inválido. Opciones: {valid_statuses}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        clinic.status = new_status
        clinic.save()

        return Response({
            'message': f'Estado cambiado a {new_status}',
            'clinic': ClinicDetailSerializer(clinic).data
        })


class ClinicMeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsClinicAdmin]
    serializer_class = ClinicUpdateSerializer

    def get_object(self):
        user = self.request.user
        clinics = Clinic.objects.filter(admins=user)
        if not clinics.exists():
            raise PermissionDenied("No administras ninguna clínica.")
        # Si administra varias, podrías recibir ?clinic_id=xxx
        clinic_id = self.request.query_params.get('clinic_id')
        if clinic_id:
            return clinics.get(id=clinic_id)
        return clinics.first()


# apps/clinics/views.py - Actualizar DoctorViewSet

@extend_schema(tags=['Clínicas'])
class DoctorViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de médicos.
    """
    queryset = Doctor.objects.all()  # Mostrar todos para admin
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['clinic', 'specialty', 'clinic__city', 'status']
    search_fields = ['user__first_name', 'user__last_name', 'bio']

    def get_serializer_class(self):
        if self.action == 'list':
            return DoctorListSerializer
        elif self.action == 'create':
            return DoctorCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DoctorUpdateSerializer
        return DoctorDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'available_slots', 'schedule']:
            return [AllowAny()]
        return [IsAuthenticated(), IsClinicAdmin()]

    def get_queryset(self):
        """Filtrar según el usuario"""
        queryset = super().get_queryset()
        user = self.request.user

        # Si es paciente o anónimo, solo ver activos
        if not user.is_authenticated or user.user_type == 'patient':
            return queryset.filter(status='active')

        # Si es doctor, ver su propio perfil y compañeros de clínica
        if user.user_type == 'doctor':
            return queryset.filter(
                models.Q(user=user) | models.Q(clinic__admins=user)
            ).distinct()

        # Admin de clínica: ver todos los de su clínica
        if user.user_type == 'clinic_admin':
            return queryset.filter(clinic__admins=user)

        # Super admin: ver todos
        return queryset

    @action(detail=True, methods=['get'])
    def available_slots(self, request, pk=None):
        """Obtener horarios disponibles de un médico"""
        from apps.appointments.models import TimeSlot

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
        return Response({
            'doctor_id': doctor.id,
            'schedule': doctor.schedule,
            'appointment_duration': doctor.clinic.appointment_duration
        })

    @action(detail=True, methods=['put'], permission_classes=[IsAuthenticated])
    def update_schedule(self, request, pk=None):
        """Actualizar horario del médico"""
        doctor = self.get_object()

        if request.user != doctor.user and request.user not in doctor.clinic.admins.all():
            raise PermissionDenied('No tienes permiso para editar este horario.')

        schedule = request.data.get('schedule')
        if schedule:
            serializer = DoctorUpdateSerializer(doctor, data={'schedule': schedule}, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            # Generar slots automáticamente para las próximas 2 semanas
            generate_slots_from_schedule(doctor)

            return Response({'message': 'Horario actualizado y slots generados.'})

        return Response({'error': 'Se requiere el campo schedule.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def generate_slots(self, request, pk=None):
        """Generar slots manualmente para un rango de fechas"""
        doctor = self.get_object()

        if request.user != doctor.user and request.user not in doctor.clinic.admins.all():
            raise PermissionDenied()

        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        if not start_date or not end_date:
            return Response(
                {'error': 'Se requieren start_date y end_date.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        count = generate_slots_from_schedule(doctor, start_date, end_date)
        return Response({'message': f'{count} slots generados correctamente.'})


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


class DoctorRegistrationView(GenericAPIView):
    """
    Endpoint para creación unificada de doctor(es).
    URL sugerida: POST /api/v1/clinics/doctors/register/  (o /api/v1/auth/doctors/ si prefieres)
    """
    permission_classes = [IsAuthenticated]  # o AllowAny si se permite registro público
    serializer_class = DoctorRegistrationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        user = result['user']
        doctors = result['doctors']
        return Response({
            'user': UserSerializer(user).data,
            'doctors': [DoctorDetailSerializer(d).data for d in doctors]
        }, status=status.HTTP_201_CREATED)


class ClinicRegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = ClinicRegisterSerializer
    queryset = Clinic.objects.all()

    def perform_create(self, serializer):
        clinic = serializer.save()
        # Enviar email a superadmins
        super_admins = User.objects.filter(user_type='super_admin', is_active=True).values_list('email', flat=True)
        if super_admins:
            send_mail(
                subject='Nueva solicitud de registro de clínica',
                message=f'Nueva clínica solicitada: {clinic.name} ({clinic.email}). Revisar en admin.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=list(super_admins),
                fail_silently=True,
            )


# ============= CLINIC REJECTION =============

@extend_schema(tags=['Clínicas'])
class ClinicRejectView(generics.GenericAPIView):
    """
    POST /api/v1/clinics/{slug}/reject/ — rechazar solicitud de clínica (solo super_admin).
    Body: { "reason": "Documentación incompleta" }
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ClinicRejectSerializer

    def post(self, request, slug=None):
        if request.user.user_type != 'super_admin':
            raise PermissionDenied('Solo super admin puede rechazar clínicas.')

        try:
            clinic = Clinic.objects.get(slug=slug)
        except Clinic.DoesNotExist:
            return Response({'error': 'Clínica no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data['reason']

        clinic.status = 'rejected'
        clinic.save(update_fields=['status'])

        # Enviar email de rechazo
        try:
            send_mail(
                subject=f'Solicitud de clínica rechazada: {clinic.name}',
                message=(
                    f'Hola,\n\n'
                    f'Lamentably, tu solicitud para registrar la clínica "{clinic.name}" ha sido rechazada.\n\n'
                    f'Motivo: {reason}\n\n'
                    f'Si tienes dudas, contacta con el equipo de soporte.\n'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[clinic.applicant_email or clinic.email],
                fail_silently=True,
            )
        except Exception:
            pass

        return Response({'message': 'Clínica rechazada correctamente.'})


# ============= CLINIC ADMIN PANEL =============

@extend_schema(tags=['Clínicas'])
class ClinicMeView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/v1/clinics/me/ — obtener/actualizar la clínica propia del clinic_admin.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ClinicDetailSerializer

    def get_object(self):
        user = self.request.user
        if user.user_type != 'clinic_admin':
            raise PermissionDenied('Solo clinic_admin puede acceder a este endpoint.')

        clinics = Clinic.objects.filter(admins=user)
        if not clinics.exists():
            raise PermissionDenied('No administras ninguna clínica.')

        # Si administra varias clínicas, permitir filtrar por query param
        clinic_id = self.request.query_params.get('clinic_id')
        if clinic_id:
            return clinics.get(id=clinic_id)
        return clinics.first()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ClinicUpdateSerializer
        return ClinicDetailSerializer


@extend_schema(tags=['Clínicas'])
class ClinicMeImagesView(generics.GenericAPIView):
    """
    POST /api/v1/clinics/me/images/ — subir imágenes a la galería de la clínica propia.
    Multipart: { "image": file, "caption": "..." }
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ClinicImageSerializer

    def get_clinic(self):
        user = self.request.user
        if user.user_type != 'clinic_admin':
            raise PermissionDenied('Solo clinic_admin puede acceder.')

        clinics = Clinic.objects.filter(admins=user)
        if not clinics.exists():
            raise PermissionDenied('No administras ninguna clínica.')

        clinic_id = self.request.query_params.get('clinic_id')
        if clinic_id:
            return clinics.get(id=clinic_id)
        return clinics.first()

    def post(self, request):
        clinic = self.get_clinic()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image_obj = serializer.save(clinic=clinic)
        return Response(
            ClinicImageSerializer(image_obj).data,
            status=status.HTTP_201_CREATED
        )

    def get(self, request):
        clinic = self.get_clinic()
        images = ClinicImage.objects.filter(clinic=clinic).order_by('order')
        serializer = ClinicImageSerializer(images, many=True)
        return Response(serializer.data)


@extend_schema(tags=['Clínicas'])
class ClinicMeStatsView(generics.GenericAPIView):
    """
    GET /api/v1/clinics/me/stats/ — estadísticas de la clínica propia.
    Retorna: citas (total, completadas, canceladas), rating, revenue, doctores.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ClinicStatsSerializer

    def get(self, request):
        user = request.user
        if user.user_type != 'clinic_admin':
            raise PermissionDenied('Solo clinic_admin puede acceder.')

        clinics = Clinic.objects.filter(admins=user)
        if not clinics.exists():
            raise PermissionDenied('No administras ninguna clínica.')

        clinic_id = request.query_params.get('clinic_id')
        if clinic_id:
            clinic = clinics.get(id=clinic_id)
        else:
            clinic = clinics.first()

        from apps.appointments.models import Appointment
        from apps.reviews.models import Review
        from decimal import Decimal

        # Estadísticas de citas
        total_appointments = Appointment.objects.filter(clinic=clinic).count()
        completed_appointments = Appointment.objects.filter(clinic=clinic, status='completed').count()
        cancelled_appointments = Appointment.objects.filter(clinic=clinic, status='cancelled').count()
        pending_appointments = Appointment.objects.filter(clinic=clinic, status='pending').count()
        completion_rate = (
            (completed_appointments / total_appointments * 100)
            if total_appointments > 0 else 0
        )

        # Estadísticas de doctores
        total_doctors = clinic.doctors.filter(status='active').count()

        # Estadísticas de reseñas
        reviews = Review.objects.filter(clinic=clinic, status='approved')
        total_reviews = reviews.count()
        average_rating = (
                reviews.aggregate(models.Avg('rating'))['rating__avg']
                or 0
        )

        # Revenue (suma de precios de servicios en citas completadas)
        total_revenue = Decimal('0.00')
        completed = Appointment.objects.filter(clinic=clinic, status='completed').select_related('service')
        for apt in completed:
            if apt.service:
                total_revenue += apt.service.price or Decimal('0.00')

        data = {
            'total_appointments': total_appointments,
            'completed_appointments': completed_appointments,
            'cancelled_appointments': cancelled_appointments,
            'pending_appointments': pending_appointments,
            'completion_rate': round(completion_rate, 2),
            'total_doctors': total_doctors,
            'total_reviews': total_reviews,
            'average_rating': round(float(average_rating), 2),
            'total_revenue': total_revenue,
        }

        serializer = self.get_serializer(data)
        return Response(serializer.data)

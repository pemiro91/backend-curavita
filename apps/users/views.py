import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework import generics, status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Address
from .permissions import IsOwnerOrAdmin
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    UserAdminCreateSerializer,
    AddressSerializer,
    ChangePasswordSerializer,
    PasswordResetSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


@extend_schema(tags=['Usuarios'])
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de usuarios.
    """
    queryset = User.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['user_type', 'is_active', 'is_verified']
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['date_joined', 'email']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action == 'admin_create':
            return UserAdminCreateSerializer
        if self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        if self.action == 'admin_create':
            return [IsAuthenticated()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return User.objects.none()
        qs = User.objects.all()
        if user.user_type in ('super_admin', 'clinic_admin'):
            has_profile = self.request.query_params.get('has_doctor_profile')
            if has_profile is not None:
                if has_profile.lower() in ('false', '0'):
                    qs = qs.filter(doctor_profile__isnull=True)
                elif has_profile.lower() in ('true', '1'):
                    qs = qs.filter(doctor_profile__isnull=False)
            return qs
        return User.objects.filter(id=user.id)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': ['Contraseña actual incorrecta.']},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Contraseña actualizada correctamente.'})

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def deactivate(self, request):
        user = request.user
        user.is_active = False
        user.save()
        return Response({'message': 'Cuenta desactivada correctamente.'})

    @action(detail=False, methods=['post'], url_path='admin-create', permission_classes=[IsAuthenticated])
    def admin_create(self, request):
        """Crear usuario desde panel admin (no requiere password_confirm)."""
        if request.user.user_type not in ('super_admin', 'clinic_admin'):
            return Response(
                {'detail': 'No tienes permiso para esta acción.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = UserAdminCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Usuarios'])
class UserRegistrationView(generics.CreateAPIView):
    """
    Vista para registro de nuevos usuarios.
    """
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Usuario registrado correctamente. Por favor verifica tu email.'
        }, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Usuarios'])
class AddressViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de direcciones.
    """
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Establecer dirección como predeterminada"""
        address = self.get_object()
        address.is_default = True
        address.save()
        return Response({'message': 'Dirección establecida como predeterminada.'})


@extend_schema(tags=['Usuarios'])
class PasswordResetRequestView(generics.GenericAPIView):
    """
    Vista para solicitar reset de contraseña.
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)  # Usar serializer
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        if not email:
            return Response(
                {'email': ['Este campo es obligatorio.']},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Enviar email con link de reset
            reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

            send_mail(
                subject='Restablecer contraseña - Health Hub Connect',
                message=f'''
                Hola {user.first_name},

                Has solicitado restablecer tu contraseña.
                Haz clic en el siguiente enlace:
                {reset_url}

                Si no solicitaste esto, ignora este email.
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )

            return Response({'message': 'Email de recuperación enviado.'})

        except User.DoesNotExist:
            # No revelar si el email existe o no
            return Response({'message': 'Email de recuperación enviado.'})


@extend_schema(tags=['Usuarios'])
class PasswordResetConfirmView(generics.GenericAPIView):
    """
    Vista para confirmar reset de contraseña.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        uid = request.data.get('uid')
        token = request.data.get('token')
        password = request.data.get('password')

        if not all([uid, token, password]):
            return Response(
                {'error': 'Todos los campos son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uid = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {'error': 'Link inválido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not default_token_generator.check_token(user, token):
            return Response(
                {'error': 'Token inválido o expirado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(password)
        user.save()

        return Response({'message': 'Contraseña actualizada correctamente.'})


@extend_schema(tags=['Usuarios'])
class EmailVerificationView(generics.GenericAPIView):
    """
    Vista para verificar email.
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        # Implementar lógica de verificación con token
        # Esto requiere un modelo de EmailVerificationToken
        return Response({'message': 'Email verificado correctamente.'})


@extend_schema(tags=['Usuarios'])
class ResendVerificationEmailView(generics.GenericAPIView):
    """
    Vista para reenviar email de verificación.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_verified:
            return Response(
                {'message': 'Tu email ya está verificado.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enviar email de verificación
        send_mail(
            subject='Verifica tu email - Health Hub Connect',
            message=f'''
            Hola {user.first_name},

            Por favor verifica tu email haciendo clic en el enlace.
            ''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

        return Response({'message': 'Email de verificación reenviado.'})


@extend_schema(tags=['Usuarios'])
class CurrentUserView(generics.RetrieveUpdateAPIView):
    """
    Vista para obtener y actualizar el usuario actual autenticado.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)

        if not serializer.is_valid():
            print("ERRORES:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(UserSerializer(user).data)

    def put(self, request, *args, **kwargs):
        """Sobrescribir perfil completo (mismo comportamiento que patch para simplificar)"""
        return self.patch(request, *args, **kwargs)

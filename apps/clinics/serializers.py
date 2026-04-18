from rest_framework import serializers

from .models import Clinic, Doctor, ClinicImage
from apps.services.serializers import SpecialtySerializer
import phonenumbers
from phonenumber_field.phonenumber import PhoneNumber


class ClinicImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicImage
        fields = ['id', 'image', 'caption', 'order']


class ClinicListSerializer(serializers.ModelSerializer):
    """Serializer para listado de clínicas (resumido)"""
    distance = serializers.FloatField(read_only=True, required=False)

    class Meta:
        model = Clinic
        fields = [
            'id', 'name', 'slug', 'city', 'state',
            'rating', 'review_count', 'logo', 'distance',
            'opening_time', 'closing_time'
        ]


class ClinicDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado de clínica"""
    images = ClinicImageSerializer(many=True, read_only=True)
    services = serializers.SerializerMethodField()
    doctors = serializers.SerializerMethodField()

    class Meta:
        model = Clinic
        fields = [
            'id', 'name', 'slug', 'description', 'email', 'phone',
            'website', 'street', 'number', 'complement', 'neighborhood',
            'city', 'state', 'zip_code', 'latitude', 'longitude',
            'logo', 'cover_image', 'images', 'rating', 'review_count',
            'opening_time', 'closing_time', 'appointment_duration',
            'allow_online_booking', 'services', 'doctors',
            'created_at'
        ]

    def get_services(self, obj):
        from apps.services.serializers import ServiceSerializer
        services = obj.services.filter(is_active=True)[:10]
        return ServiceSerializer(services, many=True).data

    def get_doctors(self, obj):
        doctors = obj.doctors.filter(status='active')[:10]
        return DoctorListSerializer(doctors, many=True).data


class DoctorListSerializer(serializers.ModelSerializer):
    """Serializer para listado de médicos"""
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    specialty_name = serializers.CharField(source='specialty.name', read_only=True)
    avatar = serializers.ImageField(source='user.avatar', read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'id', 'full_name', 'specialty_name', 'avatar',
            'experience_years', 'consultation_fee', 'rating'
        ]


class DoctorDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado de médico"""
    user = serializers.SerializerMethodField()
    specialty = SpecialtySerializer(read_only=True)
    secondary_specialties = SpecialtySerializer(many=True, read_only=True)
    clinic = ClinicListSerializer(read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'id', 'user', 'license_number', 'specialty',
            'secondary_specialties', 'bio', 'education',
            'experience_years', 'schedule', 'consultation_fee',
            'clinic', 'rating', 'review_count', 'status'
        ]

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'full_name': obj.user.full_name,
            'email': obj.user.email,
            'phone': str(obj.user.phone) if obj.user.phone else None,
            'avatar': obj.user.avatar.url if obj.user.avatar else None,
        }


class DoctorCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear médico"""
    user_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Doctor
        fields = [
            'user_id', 'license_number', 'specialty',
            'bio', 'education', 'experience_years',
            'schedule', 'consultation_fee'
        ]

    def validate_user_id(self, value):
        from apps.users.models import User
        try:
            user = User.objects.get(id=value)
            if user.user_type != 'doctor':
                raise serializers.ValidationError("El usuario no es un médico.")
            if hasattr(user, 'doctor_profile'):
                raise serializers.ValidationError("El usuario ya tiene un perfil de médico.")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Usuario no encontrado.")


# Añadir a tu serializers.py de Clinics


class ClinicCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear nuevas clínicas.
    """
    admin_emails = serializers.ListField(
        child=serializers.EmailField(),
        write_only=True,
        required=False,
        default=list  # Importante: lista vacía por defecto
    )

    class Meta:
        model = Clinic
        fields = [
            'name', 'description', 'email', 'phone', 'website',
            'street', 'number', 'complement', 'neighborhood',
            'city', 'state', 'zip_code', 'latitude', 'longitude',
            'logo', 'cover_image', 'opening_time', 'closing_time',
            'appointment_duration', 'allow_online_booking',
            'admin_emails'
        ]

    def validate_email(self, value):
        """Validar email único."""
        if Clinic.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe una clínica con este email.")
        return value

    def validate_phone(self, value):
        """Normalizar número de teléfono."""
        if not value:
            raise serializers.ValidationError("El teléfono es requerido.")

        # Si ya tiene formato internacional, validarlo
        if value.startswith('+'):
            try:
                parsed = phonenumbers.parse(value, None)
                if not phonenumbers.is_valid_number(parsed):
                    raise serializers.ValidationError("Número inválido.")
                return value
            except:
                raise serializers.ValidationError("Formato inválido. Use: +5353920566")

        # Si no tiene +, intentar con códigos de país comunes
        country_codes = ['53', '52', '1', '34', '57']  # Cuba, México, USA, España, Colombia
        for code in country_codes:
            try:
                full_number = f"+{code}{value}"
                parsed = phonenumbers.parse(full_number, None)
                if phonenumbers.is_valid_number(parsed):
                    return full_number
            except:
                continue

        # Si ninguno funciona, asumir Cuba (+53) por defecto
        return f"+53{value}"

    def validate(self, attrs):
        """Validaciones generales."""
        opening = attrs.get('opening_time')
        closing = attrs.get('closing_time')

        if opening and closing and opening >= closing:
            raise serializers.ValidationError(
                {"closing_time": "La hora de cierre debe ser posterior a la de apertura."}
            )

        # Validar coordenadas: ambas o ninguna
        lat = attrs.get('latitude')
        lng = attrs.get('longitude')

        if (lat is not None and lng is None) or (lat is None and lng is not None):
            raise serializers.ValidationError(
                {"latitude": "Debes proporcionar ambas coordenadas o ninguna."}
            )

        if lat is not None:
            try:
                lat_val = float(lat)
                lng_val = float(lng)
                if not (-90 <= lat_val <= 90):
                    raise serializers.ValidationError(
                        {"latitude": "La latitud debe estar entre -90 y 90."}
                    )
                if not (-180 <= lng_val <= 180):
                    raise serializers.ValidationError(
                        {"longitude": "La longitud debe estar entre -180 y 180."}
                    )
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    {"latitude": "Coordenadas inválidas."}
                )

        return attrs

    def create(self, validated_data):
        """Crear clínica con slug único."""
        import itertools
        from django.utils.text import slugify

        # Generar slug único
        base_slug = slugify(validated_data['name'])
        slug = base_slug

        for i in itertools.count(1):
            if not Clinic.objects.filter(slug=slug).exists():
                break
            slug = f"{base_slug}-{i}"

        validated_data['slug'] = slug
        validated_data['status'] = 'pending'

        # Remover admin_emails antes de crear
        admin_emails = validated_data.pop('admin_emails', [])

        # Crear clínica
        clinic = Clinic.objects.create(**validated_data)

        # Añadir creador como admin
        clinic.admins.add(self.context['request'].user)

        # Añadir admins adicionales
        from apps.users.models import User
        for email in admin_emails:
            try:
                user = User.objects.get(email=email)
                clinic.admins.add(user)
            except User.DoesNotExist:
                pass  # Ignorar si no existe

        return clinic


class ClinicUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar clínicas.
    """

    class Meta:
        model = Clinic
        fields = [
            'name', 'description', 'email', 'phone', 'website',
            'street', 'number', 'complement', 'neighborhood',
            'city', 'state', 'zip_code', 'latitude', 'longitude',
            'logo', 'cover_image', 'opening_time', 'closing_time',
            'appointment_duration', 'allow_online_booking', 'status'
        ]

    def validate(self, attrs):
        opening = attrs.get('opening_time', self.instance.opening_time)
        closing = attrs.get('closing_time', self.instance.closing_time)

        if opening and closing and opening >= closing:
            raise serializers.ValidationError(
                {"closing_time": "La hora de cierre debe ser posterior a la de apertura."}
            )
        return attrs

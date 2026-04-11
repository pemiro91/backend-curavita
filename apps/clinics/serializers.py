from rest_framework import serializers

from .models import Clinic, Doctor, ClinicImage
from apps.services.serializers import SpecialtySerializer


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
from rest_framework import serializers
from .models import Specialty, Service


class SpecialtySerializer(serializers.ModelSerializer):
    """
    Serializer para especialidades médicas.
    """
    doctors_count = serializers.SerializerMethodField(read_only=True)
    services_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Specialty
        fields = [
            'id', 'name', 'slug', 'description', 'icon',
            'color', 'order', 'is_active',
            'doctors_count', 'services_count', 'created_at'
        ]
        read_only_fields = ['slug', 'created_at']

    def get_doctors_count(self, obj):
        """Cuenta médicos activos con esta especialidad."""
        return obj.doctors.filter(status='active').count()

    def get_services_count(self, obj):
        """Cuenta servicios activos con esta especialidad."""
        return obj.services.filter(is_active=True).count()


class SpecialtyCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear/actualizar especialidades (solo admin).
    """

    class Meta:
        model = Specialty
        fields = [
            'id', 'name', 'description', 'icon',
            'color', 'order', 'is_active'
        ]

    def validate_name(self, value):
        """Validar que el nombre sea único (case insensitive)."""
        if self.instance:
            # En actualización, excluir el registro actual
            exists = Specialty.objects.filter(
                name__iexact=value
            ).exclude(id=self.instance.id).exists()
        else:
            exists = Specialty.objects.filter(name__iexact=value).exists()

        if exists:
            raise serializers.ValidationError("Ya existe una especialidad con este nombre.")
        return value


class ServiceSerializer(serializers.ModelSerializer):
    """
    Serializer para listado de servicios.
    """
    specialty_name = serializers.CharField(source='specialty.name', read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    duration_display = serializers.CharField(source='get_duration_display', read_only=True)

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'clinic', 'clinic_name',
            'specialty', 'specialty_name', 'service_type',
            'price', 'duration_minutes', 'duration_display',
            'is_active', 'requires_preparation'
        ]
        # read_only_fields = ['slug']


class ServiceDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para un servicio específico.
    """
    specialty = SpecialtySerializer(read_only=True)
    clinic = serializers.SerializerMethodField()
    preparation_instructions = serializers.CharField(read_only=True)

    class Meta:
        model = Service
        fields = [
            'id', 'name',  'description', 'clinic',
            'specialty', 'service_type', 'price', 'duration_minutes',
            'preparation_instructions', 'is_active',
            'requires_preparation',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_clinic(self, obj):
        """Retorna info resumida de la clínica."""
        from apps.clinics.serializers import ClinicListSerializer
        return ClinicListSerializer(obj.clinic).data


class ServiceCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear nuevos servicios.
    """

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'clinic', 'specialty',
            'service_type', 'price', 'duration_minutes',
            'preparation_instructions', 'requires_preparation',

        ]

    def validate_price(self, value):
        """Validar que el precio sea positivo."""
        if value < 0:
            raise serializers.ValidationError("El precio no puede ser negativo.")
        return value

    def validate_duration_minutes(self, value):
        """Validar duración mínima y máxima."""
        if value < 5:
            raise serializers.ValidationError("La duración mínima es 5 minutos.")
        if value > 480:  # 8 horas
            raise serializers.ValidationError("La duración máxima es 8 horas.")
        return value

    def validate(self, attrs):
        """Validar que el usuario sea admin de la clínica."""
        clinic = attrs.get('clinic')
        user = self.context['request'].user

        # Verificar que el usuario sea admin de la clínica
        if user.user_type == 'super_admin':
            return attrs

        if not clinic.admins.filter(id=user.id).exists():
            raise serializers.ValidationError(
                {"clinic": "No eres administrador de esta clínica."}
            )

        return attrs

    def create(self, validated_data):
        """Crear el servicio con slug automático."""
        import re
        from django.utils.text import slugify

        # Generar slug único
        base_slug = slugify(validated_data['name'])
        slug = base_slug
        counter = 1

        while Service.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        validated_data['slug'] = slug
        return super().create(validated_data)


class ServiceUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar servicios existentes.
    """

    class Meta:
        model = Service
        fields = [
            'name', 'description', 'specialty', 'price',
            'duration_minutes', 'preparation_instructions',
            'requires_preparation',
            'is_active'
        ]

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("El precio no puede ser negativo.")
        return value

    def validate_duration_minutes(self, value):
        if value < 5:
            raise serializers.ValidationError("La duración mínima es 5 minutos.")
        if value > 480:
            raise serializers.ValidationError("La duración máxima es 8 horas.")
        return value


class ServiceBulkUpdateSerializer(serializers.Serializer):
    """
    Serializer para actualizar múltiples servicios a la vez.
    """
    service_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True
    )
    is_active = serializers.BooleanField(required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    def validate_service_ids(self, value):
        """Validar que todos los servicios existan."""
        existing_ids = set(
            Service.objects.filter(
                id__in=value
            ).values_list('id', flat=True)
        )
        missing = set(value) - existing_ids
        if missing:
            raise serializers.ValidationError(
                f"Servicios no encontrados: {missing}"
            )
        return value
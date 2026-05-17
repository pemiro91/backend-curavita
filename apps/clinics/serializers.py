from django.db import transaction
from rest_framework import serializers

from apps.services.models import Specialty
from apps.services.serializers import SpecialtySerializer
from apps.users.models import User
from apps.users.serializers import UserCreateSerializer  # reutilizar validaciones de usuario
from .models import Clinic, Doctor, ClinicImage


class ClinicImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicImage
        fields = ['id', 'image', 'caption', 'order']


class ClinicListSerializer(serializers.ModelSerializer):
    """Serializer para listado de clínicas (resumido)"""
    distance = serializers.FloatField(read_only=True, required=False)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Clinic
        fields = [
            'id', 'name', 'email', 'phone', 'website', 'description',
            'street', 'number', 'slug', 'city', 'state',
            'complement', 'neighborhood', 'zip_code', 'latitude',
            'longitude', 'appointment_duration', 'rating',
            'review_count', 'logo', 'distance', 'opening_time',
            'closing_time', 'is_active', 'allow_online_booking', 'cover_image',
            'status', 'status_display'
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
            'created_at', 'is_active'
        ]
        read_only_fields = ["approved_at", "approved_by"]

    def get_services(self, obj):
        from apps.services.serializers import ServiceSerializer
        services = obj.services.filter(is_active=True)[:10]
        return ServiceSerializer(services, many=True).data

    def get_doctors(self, obj):
        doctors = obj.doctors.filter(status='active')[:10]
        return DoctorListSerializer(doctors, many=True).data


class ClinicRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        exclude = ["logo", "cover_image", "status", "approved_at",
                   "approved_by", "rating", "review_count", "admins"]

    def create(self, validated_data):
        validated_data["status"] = "pending_approval"
        return super().create(validated_data)


class DoctorListSerializer(serializers.ModelSerializer):
    """Serializer para listado de médicos"""
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    specialty_name = serializers.CharField(source='specialty.name', read_only=True)
    avatar = serializers.ImageField(source='user.avatar', read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'id', 'full_name', 'specialty_name', 'avatar',
            'experience_years', 'consultation_fee', 'rating',
            'clinic_name', 'status'
        ]


# Serializer para el payload unificado
class DoctorRegistrationSerializer(serializers.Serializer):
    user = UserCreateSerializer()
    profile = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        default=dict
    )
    specialties = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list
    )
    clinics = serializers.ListField(
        child=serializers.UUIDField(),
        required=True
    )
    schedule = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )

    def validate_specialties(self, value):
        missing = [str(s) for s in value if not Specialty.objects.filter(id=s).exists()]
        if missing:
            raise serializers.ValidationError(f"Specialties not found: {', '.join(missing)}")
        return value

    def validate_clinics(self, value):
        """Validar que existan todas las clínicas."""
        missing = [str(c) for c in value if not Clinic.objects.filter(id=c).exists()]
        if missing:
            raise serializers.ValidationError(f"Clinics not found: {', '.join(missing)}")
        if not value:
            raise serializers.ValidationError("At least one clinic is required.")
        return value

    def _normalize_schedule(self, slots):
        """
        Convierte lista de slots a JSON esperado por Doctor.schedule.
        Input: [{"weekday": 0, "start_time": "08:00", "end_time": "12:00"}, ...]
        Output: {"monday": [{"start": "08:00", "end": "12:00"}], ...}
        """
        days_map = {
            0: 'monday', 1: 'tuesday', 2: 'wednesday',
            3: 'thursday', 4: 'friday', 5: 'saturday', 6: 'sunday'
        }
        result = {}
        for slot in slots:
            try:
                weekday = int(slot.get('weekday'))
                day_key = days_map.get(weekday)
                if not day_key:
                    continue

                start_time = slot.get('start_time')
                end_time = slot.get('end_time')

                if not start_time or not end_time:
                    continue

                result.setdefault(day_key, [])
                result[day_key].append({
                    'start': start_time,
                    'end': end_time
                })
            except (ValueError, TypeError):
                continue
        return result

    def create(self, validated_data):
        """
        Crear User + Doctor(s) en transacción atómica.
        - Crea User con user_type='doctor'.
        - Crea un Doctor por cada clinic indicada.
        - Asigna specialties (primera = primary, resto = secondary).
        - Guarda schedule.
        """
        user_data = validated_data['user']
        profile_data = validated_data.get('profile', {})
        specialties_ids = validated_data.get('specialties', [])
        clinics_ids = validated_data['clinics']
        schedule_input = validated_data.get('schedule', [])

        # Normalizar schedule a JSON
        schedule_json = self._normalize_schedule(schedule_input)

        with transaction.atomic():
            # Crear usuario (reutiliza UserCreateSerializer)
            user_serializer = UserCreateSerializer(data=user_data)
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()

            # Resolver specialties
            primary_specialty = None
            secondary_specialties = []
            if specialties_ids:
                primary_specialty = Specialty.objects.get(id=specialties_ids[0])
                if len(specialties_ids) > 1:
                    secondary_specialties = list(Specialty.objects.filter(id__in=specialties_ids[1:]))

            # Crear un Doctor por cada clinic
            created_doctors = []
            for clinic_id in clinics_ids:
                clinic = Clinic.objects.get(id=clinic_id)
                doctor = Doctor.objects.create(
                    user=user,
                    clinic=clinic,
                    license_number=profile_data.get('license_number', ''),
                    bio=profile_data.get('biography', ''),
                    consultation_fee=profile_data.get('consultation_price') or 0,
                    experience_years=int(profile_data.get('years_of_experience', 0) or 0),
                    schedule=schedule_json,
                    specialty=primary_specialty if primary_specialty else None,
                )
                # Asignar specialties secundarias
                if secondary_specialties:
                    for spec in secondary_specialties:
                        doctor.secondary_specialties.add(spec)
                created_doctors.append(doctor)

        return {'user': user, 'doctors': created_doctors}


class DoctorDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado de médico"""
    user = serializers.SerializerMethodField()
    specialty = SpecialtySerializer(read_only=True)
    clinic = ClinicListSerializer(read_only=True)
    schedule_display = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = [
            'id', 'user', 'license_number', 'specialty',
            'secondary_specialties', 'bio', 'education',
            'experience_years', 'schedule', 'schedule_display',
            'consultation_fee', 'clinic', 'rating', 'review_count', 'status'
        ]

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'full_name': obj.user.full_name,
            'email': obj.user.email,
            'phone': str(obj.user.phone) if obj.user.phone else None,
            'avatar': obj.user.avatar.url if obj.user.avatar else None,
        }

    def get_schedule_display(self, obj):
        """Convertir schedule JSON a formato legible"""
        schedule = obj.schedule or {}
        days_map = {
            'monday': 'Lunes', 'tuesday': 'Martes', 'wednesday': 'Miércoles',
            'thursday': 'Jueves', 'friday': 'Viernes', 'saturday': 'Sábado', 'sunday': 'Domingo'
        }
        result = []
        for day, slots in schedule.items():
            if slots:
                result.append({
                    'day': days_map.get(day, day),
                    'day_key': day,
                    'slots': slots
                })
        return result


class DoctorCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear médico"""
    user_id = serializers.UUIDField(write_only=True)
    schedule = serializers.JSONField(required=False, default=dict)

    class Meta:
        model = Doctor
        fields = [
            'user_id', 'clinic', 'license_number', 'specialty',
            'bio', 'education', 'experience_years',
            'schedule', 'consultation_fee'
        ]

    def validate_user_id(self, value):

        try:
            user = User.objects.get(id=value)
            if user.user_type != 'doctor':
                raise serializers.ValidationError("El usuario no es un médico.")
            if hasattr(user, 'doctor_profile'):
                raise serializers.ValidationError("El usuario ya tiene un perfil de médico.")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Usuario no encontrado.")

    def validate_schedule(self, value):
        """Validar formato del horario"""
        if not value:
            return {}

        valid_days = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}

        if not isinstance(value, dict):
            raise serializers.ValidationError("El horario debe ser un objeto JSON.")

        for day, slots in value.items():
            if day not in valid_days:
                raise serializers.ValidationError(f"Día inválido: {day}")
            if not isinstance(slots, list):
                raise serializers.ValidationError(f"Los slots de {day} deben ser una lista.")
            for slot in slots:
                if not isinstance(slot, dict) or 'start' not in slot or 'end' not in slot:
                    raise serializers.ValidationError(f"Formato de slot inválido en {day}")

        return value

    def create(self, validated_data):
        user_id = validated_data.pop('user_id')
        from apps.users.models import User
        user = User.objects.get(id=user_id)

        doctor = Doctor.objects.create(user=user, **validated_data)
        return doctor


class DoctorUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar médico"""
    schedule = serializers.JSONField(required=False)

    class Meta:
        model = Doctor
        fields = [
            'license_number', 'specialty', 'bio', 'education',
            'experience_years', 'schedule', 'consultation_fee', 'status'
        ]

    def validate_user_id(self, value):

        try:
            user = User.objects.get(id=value)
            if user.user_type != 'doctor':
                raise serializers.ValidationError("El usuario no es un médico.")
            if hasattr(user, 'doctor_profile'):
                raise serializers.ValidationError("El usuario ya tiene un perfil de médico.")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Usuario no encontrado.")

    def validate_schedule(self, value):
        """Validar formato del horario"""
        if not value:
            return {}

        valid_days = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}

        if not isinstance(value, dict):
            raise serializers.ValidationError("El horario debe ser un objeto JSON.")

        for day, slots in value.items():
            if day not in valid_days:
                raise serializers.ValidationError(f"Día inválido: {day}")
            if not isinstance(slots, list):
                raise serializers.ValidationError(f"Los slots de {day} deben ser una lista.")
            for slot in slots:
                if not isinstance(slot, dict) or 'start' not in slot or 'end' not in slot:
                    raise serializers.ValidationError(f"Formato de slot inválido en {day}")

        return value


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
        """Validar teléfono con formato internacional."""
        if not value:
            raise serializers.ValidationError("El teléfono es requerido.")

        # Limpiar
        value = value.strip().replace(" ", "")

        # Debe empezar con + y tener solo dígitos después
        if not value.startswith('+'):
            raise serializers.ValidationError("El número debe incluir el prefijo internacional (ej: +5353920566)")

        digits = value[1:].replace("-", "")
        if not digits.isdigit():
            raise serializers.ValidationError("El número solo debe contener dígitos después del +")

        if len(digits) < 7:
            raise serializers.ValidationError("Número demasiado corto.")

        if len(digits) > 15:
            raise serializers.ValidationError("Número demasiado largo.")

        return value

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


# ============= CLINIC REJECTION & PANEL ENDPOINTS =============

class ClinicRejectSerializer(serializers.Serializer):
    """Serializer para rechazar solicitud de clínica."""
    reason = serializers.CharField(required=True, max_length=500)


class ClinicStatsSerializer(serializers.Serializer):
    """Serializer para estadísticas de clínica."""
    total_appointments = serializers.IntegerField()
    completed_appointments = serializers.IntegerField()
    cancelled_appointments = serializers.IntegerField()
    pending_appointments = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    total_doctors = serializers.IntegerField()
    total_reviews = serializers.IntegerField()
    average_rating = serializers.FloatField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)

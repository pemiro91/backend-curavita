from rest_framework import serializers
from django.utils import timezone

from .models import Appointment, TimeSlot


class TimeSlotSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)

    class Meta:
        model = TimeSlot
        fields = ['id', 'date', 'start_time', 'end_time', 'doctor_name', 'is_available']


class AppointmentListSerializer(serializers.ModelSerializer):
    """Serializer para listado de citas"""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'appointment_number', 'patient_name',
            'doctor_name', 'clinic_name', 'service_name',
            'date', 'start_time', 'end_time', 'status'
        ]


class AppointmentDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado de cita"""
    patient = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()
    clinic = serializers.SerializerMethodField()
    service = serializers.SerializerMethodField()
    can_cancel = serializers.BooleanField(read_only=True)
    can_reschedule = serializers.BooleanField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'appointment_number', 'patient', 'doctor',
            'clinic', 'service', 'date', 'start_time', 'end_time',
            'status', 'patient_notes', 'doctor_notes',
            'can_cancel', 'can_reschedule',
            'created_at', 'updated_at'
        ]

    def get_patient(self, obj):
        return {
            'id': obj.patient.id,
            'full_name': obj.patient.full_name,
            'email': obj.patient.email,
            'phone': str(obj.patient.phone) if obj.patient.phone else None,
        }

    def get_doctor(self, obj):
        return {
            'id': obj.doctor.id,
            'full_name': obj.doctor.user.full_name,
            'specialty': obj.doctor.specialty.name,
        }

    def get_clinic(self, obj):
        return {
            'id': obj.clinic.id,
            'name': obj.clinic.name,
            'address': f"{obj.clinic.street}, {obj.clinic.number}",
            'city': obj.clinic.city,
        }

    def get_service(self, obj):
        return {
            'id': obj.service.id,
            'name': obj.service.name,
            'duration_minutes': obj.service.duration_minutes,
            'price': str(obj.service.price),
        }


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear cita"""

    class Meta:
        model = Appointment
        fields = [
            'clinic', 'doctor', 'service',
            'date', 'start_time', 'patient_notes'
        ]

    def validate(self, attrs):
        # Validar que el horario esté disponible
        doctor = attrs['doctor']
        date = attrs['date']
        start_time = attrs['start_time']

        # Verificar que no exista otra cita
        existing = Appointment.objects.filter(
            doctor=doctor,
            date=date,
            start_time=start_time,
            status__in=['pending', 'confirmed']
        ).exists()

        if existing:
            raise serializers.ValidationError(
                {"start_time": "Este horario ya no está disponible."}
            )

        # Validar que la fecha no sea en el pasado
        appointment_datetime = timezone.make_aware(
            timezone.datetime.combine(date, start_time)
        )
        if appointment_datetime < timezone.now():
            raise serializers.ValidationError(
                {"date": "No puedes agendar citas en el pasado."}
            )

        return attrs

    def create(self, validated_data):
        validated_data['patient'] = self.context['request'].user
        validated_data['status'] = 'pending'
        return super().create(validated_data)


class AppointmentCancelSerializer(serializers.Serializer):
    """Serializer para cancelar cita"""
    reason = serializers.ChoiceField(
        choices=Appointment.CancellationReason.choices,
        required=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        appointment = self.context['appointment']
        if not appointment.can_cancel:
            raise serializers.ValidationError(
                "Esta cita no puede ser cancelada."
            )
        return attrs


class AvailableSlotsSerializer(serializers.Serializer):
    """Serializer para consultar horarios disponibles"""
    doctor_id = serializers.UUIDField(required=True)
    date = serializers.DateField(required=True)

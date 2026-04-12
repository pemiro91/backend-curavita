from django.utils import timezone
from rest_framework import serializers

from .models import Appointment, TimeSlot, AppointmentHistory


class TimeSlotSerializer(serializers.ModelSerializer):
    """
    Serializer para horarios disponibles.
    """
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
    doctor_id = serializers.UUIDField(source='doctor.id', read_only=True)

    class Meta:
        model = TimeSlot
        fields = [
            'id', 'doctor_id', 'doctor_name', 'date',
            'start_time', 'end_time', 'is_available', 'is_blocked'
        ]
        read_only_fields = ['id']


class TimeSlotCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear horarios disponibles.
    Solo clínicas pueden crear horarios.
    """

    class Meta:
        model = TimeSlot
        fields = ['doctor', 'date', 'start_time', 'end_time', 'is_available']

    def validate(self, attrs):
        doctor = attrs.get('doctor')
        date = attrs.get('date')
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')

        # Validar que el horario no se solape con otro existente
        overlapping = TimeSlot.objects.filter(
            doctor=doctor,
            date=date,
            start_time__lt=end_time,
            end_time__gt=start_time
        ).exists()

        if overlapping:
            raise serializers.ValidationError(
                "Este horario se solapa con otro existente."
            )

        # Validar que la hora de inicio sea menor que la de fin
        if start_time >= end_time:
            raise serializers.ValidationError(
                "La hora de inicio debe ser menor que la hora de fin."
            )

        return attrs


class TimeSlotBlockSerializer(serializers.Serializer):
    """
    Serializer para bloquear/desbloquear horarios.
    """
    is_blocked = serializers.BooleanField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AppointmentListSerializer(serializers.ModelSerializer):
    """
    Serializer para listado de citas.
    """
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.get_full_name', read_only=True)
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
    """
    Serializer detallado de cita.
    """
    patient = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()
    clinic = serializers.SerializerMethodField()
    service = serializers.SerializerMethodField()
    can_cancel = serializers.BooleanField(read_only=True)
    can_reschedule = serializers.BooleanField(read_only=True)
    cancellation_info = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id', 'appointment_number', 'patient', 'doctor',
            'clinic', 'service', 'date', 'start_time', 'end_time',
            'status', 'patient_notes', 'doctor_notes',
            'can_cancel', 'can_reschedule', 'cancellation_info',
            'created_at', 'updated_at'
        ]

    def get_patient(self, obj):
        return {
            'id': obj.patient.id,
            'full_name': obj.patient.get_full_name(),
            'email': obj.patient.email,
            'phone': str(obj.patient.phone) if hasattr(obj.patient, 'phone') and obj.patient.phone else None,
        }

    def get_doctor(self, obj):
        return {
            'id': obj.doctor.id,
            'full_name': obj.doctor.user.get_full_name(),
            'specialty': obj.doctor.specialty.name if hasattr(obj.doctor,
                                                              'specialty') and obj.doctor.specialty else None,
        }

    def get_clinic(self, obj):
        return {
            'id': obj.clinic.id,
            'name': obj.clinic.name,
            'address': f"{obj.clinic.street} {obj.clinic.number}" if hasattr(obj.clinic,
                                                                             'street') else obj.clinic.address,
            'city': obj.clinic.city if hasattr(obj.clinic, 'city') else None,
        }

    def get_service(self, obj):
        return {
            'id': obj.service.id,
            'name': obj.service.name,
            'duration_minutes': obj.service.duration_minutes if hasattr(obj.service, 'duration_minutes') else None,
            'price': str(obj.service.price) if hasattr(obj.service, 'price') else None,
        }

    def get_cancellation_info(self, obj):
        if obj.status == 'cancelled':
            return {
                'cancelled_by': obj.cancelled_by.get_full_name() if obj.cancelled_by else None,
                'cancelled_at': obj.cancelled_at,
                'reason': obj.cancellation_reason,
                'notes': obj.cancellation_notes,
            }
        return None


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear cita.
    """

    class Meta:
        model = Appointment
        fields = [
            'clinic', 'doctor', 'service',
            'date', 'start_time', 'patient_notes'
        ]

    def validate(self, attrs):
        doctor = attrs.get('doctor')
        date = attrs.get('date')
        start_time = attrs.get('start_time')
        clinic = attrs.get('clinic')
        service = attrs.get('service')

        # Validar que el doctor pertenezca a la clínica
        if hasattr(doctor, 'clinic') and doctor.clinic != clinic:
            raise serializers.ValidationError(
                {"doctor": "Este doctor no pertenece a la clínica seleccionada."}
            )

        # Verificar que el horario esté disponible en TimeSlot
        slot_available = TimeSlot.objects.filter(
            doctor=doctor,
            date=date,
            start_time=start_time,
            is_available=True,
            is_blocked=False
        ).exists()

        if not slot_available:
            raise serializers.ValidationError(
                {"start_time": "Este horario no está disponible."}
            )

        # Verificar que no exista otra cita confirmada/pendiente en ese horario
        existing = Appointment.objects.filter(
            doctor=doctor,
            date=date,
            start_time=start_time,
            status__in=['pending', 'confirmed', 'checked_in', 'in_progress']
        ).exists()

        if existing:
            raise serializers.ValidationError(
                {"start_time": "Este horario ya está reservado."}
            )

        # Validar que la fecha no sea en el pasado
        appointment_datetime = timezone.make_aware(
            timezone.datetime.combine(date, start_time)
        )
        if appointment_datetime < timezone.now():
            raise serializers.ValidationError(
                {"date": "No puedes agendar citas en el pasado."}
            )

        # Validar que la fecha no sea muy lejana (ej. máximo 3 meses)
        max_date = timezone.now() + timezone.timedelta(days=90)
        if date > max_date.date():
            raise serializers.ValidationError(
                {"date": "No puedes agendar citas con más de 3 meses de anticipación."}
            )

        return attrs

    def create(self, validated_data):
        # Generar número de cita único
        import uuid
        validated_data['appointment_number'] = f"APT-{uuid.uuid4().hex[:8].upper()}"
        validated_data['patient'] = self.context['request'].user
        validated_data['status'] = 'pending'

        # Bloquear el horario
        TimeSlot.objects.filter(
            doctor=validated_data['doctor'],
            date=validated_data['date'],
            start_time=validated_data['start_time']
        ).update(is_available=False)

        return super().create(validated_data)


class AppointmentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar cita (solo notas, no fecha/hora/doctor).
    """

    class Meta:
        model = Appointment
        fields = ['patient_notes', 'doctor_notes']

    def validate(self, attrs):
        appointment = self.instance

        # Solo permitir actualizar notas si la cita está activa
        if appointment.status in ['cancelled', 'completed', 'no_show']:
            raise serializers.ValidationError(
                "No se pueden modificar citas finalizadas o canceladas."
            )

        return attrs


class AppointmentRescheduleSerializer(serializers.Serializer):
    """
    Serializer para reagendar cita.
    """
    date = serializers.DateField(required=True)
    start_time = serializers.TimeField(required=True)

    def validate(self, attrs):
        appointment = self.context.get('appointment')
        new_date = attrs.get('date')
        new_time = attrs.get('start_time')

        if not appointment.can_reschedule:
            raise serializers.ValidationError(
                "Esta cita no puede ser reagendada."
            )

        # Validar que el nuevo horario esté disponible
        doctor = appointment.doctor

        slot_available = TimeSlot.objects.filter(
            doctor=doctor,
            date=new_date,
            start_time=new_time,
            is_available=True,
            is_blocked=False
        ).exists()

        if not slot_available:
            raise serializers.ValidationError(
                {"start_time": "Este horario no está disponible."}
            )

        # Validar que no sea en el pasado
        new_datetime = timezone.make_aware(
            timezone.datetime.combine(new_date, new_time)
        )
        if new_datetime < timezone.now():
            raise serializers.ValidationError(
                {"date": "No puedes reagendar a una fecha pasada."}
            )

        return attrs


class AppointmentCancelSerializer(serializers.Serializer):
    """
    Serializer para cancelar cita.
    """
    reason = serializers.ChoiceField(
        choices=[
            ('patient_request', 'Solicitud del paciente'),
            ('doctor_unavailable', 'Doctor no disponible'),
            ('emergency', 'Emergencia'),
            ('other', 'Otro'),
        ],
        required=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        appointment = self.context.get('appointment')
        if not appointment.can_cancel:
            raise serializers.ValidationError(
                "Esta cita no puede ser cancelada."
            )
        return attrs


class AppointmentConfirmSerializer(serializers.Serializer):
    """
    Serializer para confirmar cita (vacío, solo valida permisos).
    """
    pass


class AppointmentCompleteSerializer(serializers.Serializer):
    """
    Serializer para completar cita.
    """
    doctor_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class AppointmentCheckInSerializer(serializers.Serializer):
    """
    Serializer para check-in de cita.
    """
    pass


class AppointmentHistorySerializer(serializers.ModelSerializer):
    """
    Serializer para historial de cambios de citas.
    """
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AppointmentHistory
        fields = [
            'id', 'appointment', 'action', 'previous_status', 'new_status', 'status_display',
            'changed_by_name', 'notes', 'created_at'
        ]
        read_only_fields = fields


class AvailableSlotsQuerySerializer(serializers.Serializer):
    """
    Serializer para consultar horarios disponibles.
    """
    doctor_id = serializers.UUIDField(required=True)
    date = serializers.DateField(required=True)

    def validate_date(self, value):
        # No permitir fechas en el pasado
        if value < timezone.now().date():
            raise serializers.ValidationError("No puedes consultar fechas pasadas.")
        return value

    def validate(self, attrs):
        # Validar que el doctor existe
        from apps.clinics.models import Doctor
        try:
            Doctor.objects.get(id=attrs['doctor_id'])
        except Doctor.DoesNotExist:
            raise serializers.ValidationError(
                {"doctor_id": "Médico no encontrado."}
            )
        return attrs


class AppointmentStatsSerializer(serializers.Serializer):
    """
    Serializer para estadísticas de citas.
    """
    total_appointments = serializers.IntegerField()
    completed_appointments = serializers.IntegerField()
    cancelled_appointments = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    pending_appointments = serializers.IntegerField(required=False)
    no_show_appointments = serializers.IntegerField(required=False)


class AppointmentActionResponseSerializer(serializers.Serializer):
    """
    Serializer para respuestas de acciones sobre citas (cancelar, confirmar, etc.)
    """
    message = serializers.CharField()
    appointment_id = serializers.UUIDField(required=False)
    status = serializers.CharField(required=False)

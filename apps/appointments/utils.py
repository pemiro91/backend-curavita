# apps/appointments/utils.py
from datetime import datetime, timedelta, time
from django.utils import timezone
from .models import TimeSlot


def generate_slots_from_schedule(doctor, start_date=None, end_date=None, days_ahead=14):
    """
    Genera slots automáticamente basado en el horario semanal del doctor.

    Args:
        doctor: Instancia de Doctor
        start_date: Fecha inicio (string YYYY-MM-DD o None para hoy)
        end_date: Fecha fin (string YYYY-MM-DD o None para start_date + days_ahead)
        days_ahead: Días a generar si no se especifica end_date
    """
    from apps.clinics.models import Doctor

    if not doctor.schedule:
        return 0

    # Parsear fechas
    if start_date:
        current = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        current = timezone.now().date()

    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end = current + timedelta(days=days_ahead)

    schedule = doctor.schedule
    clinic_duration = doctor.clinic.appointment_duration or 30  # minutos por defecto

    created_count = 0

    # Iterar día por día
    while current <= end:
        day_name = current.strftime('%A').lower()  # monday, tuesday, etc.

        if day_name in schedule and schedule[day_name]:
            for slot_range in schedule[day_name]:
                start_time = datetime.strptime(slot_range['start'], '%H:%M').time()
                end_time = datetime.strptime(slot_range['end'], '%H:%M').time()

                # Generar slots de duración fija dentro del rango
                slot_start = datetime.combine(current, start_time)
                slot_end = datetime.combine(current, end_time)

                while slot_start < slot_end:
                    next_slot = slot_start + timedelta(minutes=clinic_duration)

                    if next_slot > slot_end:
                        break

                    # Crear o actualizar slot
                    slot, created = TimeSlot.objects.get_or_create(
                        doctor=doctor,
                        date=current,
                        start_time=slot_start.time(),
                        defaults={
                            'end_time': next_slot.time(),
                            'is_available': True,
                            'is_blocked': False
                        }
                    )

                    if created:
                        created_count += 1

                    slot_start = next_slot

        current += timedelta(days=1)

    return created_count


def cleanup_old_slots(doctor=None, days_past=30):
    """
    Elimina slots antiguos para mantener la base de datos limpia.

    Args:
        doctor: Doctor específico o None para todos
        days_past: Eliminar slots más antiguos que estos días
    """
    cutoff_date = timezone.now().date() - timedelta(days=days_past)

    queryset = TimeSlot.objects.filter(date__lt=cutoff_date)
    if doctor:
        queryset = queryset.filter(doctor=doctor)

    count, _ = queryset.delete()
    return count


def block_time_slot(doctor, date, start_time, end_time=None, reason=""):
    """
    Bloquea un slot específico (vacaciones, emergencias, etc.)
    """
    slots = TimeSlot.objects.filter(
        doctor=doctor,
        date=date,
        start_time__gte=start_time
    )

    if end_time:
        slots = slots.filter(end_time__lte=end_time)

    updated = slots.update(is_blocked=True, blocked_reason=reason)

    # Cancelar citas existentes en esos slots
    from .models import Appointment
    appointments = Appointment.objects.filter(
        doctor=doctor,
        date=date,
        start_time__gte=start_time,
        status__in=['pending', 'confirmed']
    )

    if end_time:
        appointments = appointments.filter(start_time__lt=end_time)

    for apt in appointments:
        apt.status = 'cancelled'
        apt.cancellation_reason = 'doctor_unavailable'
        apt.cancellation_notes = reason
        apt.save()

    return updated
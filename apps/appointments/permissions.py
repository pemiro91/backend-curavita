# apps/appointments/permissions.py
from rest_framework import permissions


class IsAppointmentParticipant(permissions.BasePermission):
    """Permiso para participantes de la cita"""

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.user_type == 'super_admin':
            return True

        if user.user_type == 'clinic_admin' and user in obj.clinic.admins.all():
            return True

        if user.user_type == 'doctor' and obj.doctor.user == user:
            return True

        return obj.patient == user

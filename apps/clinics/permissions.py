# apps/clinics/permissions.py
from rest_framework import permissions


class IsClinicAdminOrReadOnly(permissions.BasePermission):
    """Permiso para admins de clínica"""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if request.user.user_type == 'super_admin':
            return True

        return request.user in obj.admins.all()


class IsClinicAdmin(permissions.BasePermission):
    """Permiso solo para admins de clínica"""

    def has_permission(self, request, view):
        return request.user.user_type in ['clinic_admin', 'super_admin']
from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permiso que permite acceso solo al dueño del objeto o a un admin.
    """

    def has_object_permission(self, request, view, obj):
        # Permitir si es el mismo usuario
        if obj.id == request.user.id:
            return True

        # Permitir si es super admin
        if hasattr(request.user, 'user_type') and request.user.user_type == 'super_admin':
            return True

        # Permitir si es staff de Django
        if request.user.is_staff:
            return True

        return False


class IsPatient(permissions.BasePermission):
    """
    Permiso que verifica que el usuario sea un paciente.
    """

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                hasattr(request.user, 'user_type') and
                request.user.user_type == 'patient'
        )


class IsDoctor(permissions.BasePermission):
    """
    Permiso que verifica que el usuario sea un médico.
    """

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                hasattr(request.user, 'user_type') and
                request.user.user_type == 'doctor'
        )


class IsSuperAdmin(permissions.BasePermission):
    """
    Permiso que verifica que el usuario sea super admin.
    """

    def has_permission(self, request, view):
        return (
                request.user and
                request.user.is_authenticated and
                hasattr(request.user, 'user_type') and
                request.user.user_type == 'super_admin'
        )

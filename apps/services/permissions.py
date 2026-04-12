from rest_framework import permissions


class IsClinicAdminOrReadOnly(permissions.BasePermission):
    """
    Permiso que permite lectura a cualquiera,
    pero solo permite escritura a admins de la clínica o super admin.
    """

    def has_permission(self, request, view):
        # Permitir lectura sin autenticación
        if request.method in permissions.SAFE_METHODS:
            return True

        # Requiere autenticación para escritura
        if not request.user or not request.user.is_authenticated:
            return False

        # Super admin puede todo
        if hasattr(request.user, 'user_type') and request.user.user_type == 'super_admin':
            return True

        return True  # La validación específica por objeto está en has_object_permission

    def has_object_permission(self, request, view, obj):
        # Permitir lectura sin autenticación
        if request.method in permissions.SAFE_METHODS:
            return True

        # Super admin puede todo
        if hasattr(request.user, 'user_type') and request.user.user_type == 'super_admin':
            return True

        # Verificar si es admin de la clínica del servicio
        if hasattr(obj, 'clinic'):
            return obj.clinic.admins.filter(id=request.user.id).exists()

        return False


class IsSuperAdminOrReadOnly(permissions.BasePermission):
    """
    Solo super admin puede modificar, cualquiera puede leer.
    Usado para Specialty.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
                request.user and
                request.user.is_authenticated and
                hasattr(request.user, 'user_type') and
                request.user.user_type == 'super_admin'
        )
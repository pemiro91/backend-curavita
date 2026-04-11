# apps/users/permissions.py
from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permiso para que solo el dueño o admin pueda editar"""

    def has_object_permission(self, request, view, obj):
        # Admin puede todo
        if request.user.user_type == 'super_admin':
            return True
        # Solo el dueño puede editar su perfil
        return obj.id == request.user.id

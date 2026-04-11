# apps/reviews/permissions.py
from rest_framework import permissions


class IsReviewOwnerOrReadOnly(permissions.BasePermission):
    """Permiso para dueño de reseña o solo lectura"""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.patient == request.user
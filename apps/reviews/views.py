# apps/reviews/views.py
import logging
from django.db.models import Avg, Count
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import Review, ReviewHelpful
from .serializers import (
    ReviewSerializer,
    ReviewCreateSerializer,
    ReviewDetailSerializer,
    ReviewHelpfulSerializer,
)
from .permissions import IsReviewOwnerOrReadOnly

logger = logging.getLogger(__name__)


class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestión de reseñas.
    """
    queryset = Review.objects.filter(status='approved')
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['clinic', 'doctor', 'rating']
    ordering_fields = ['created_at', 'rating', 'helpful_count']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return ReviewCreateSerializer
        elif self.action == 'retrieve':
            return ReviewDetailSerializer
        return ReviewSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated(), IsReviewOwnerOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(patient=self.request.user)

    @action(detail=True, methods=['post'])
    def helpful(self, request, pk=None):
        """Marcar reseña como útil"""
        review = self.get_object()

        helpful, created = ReviewHelpful.objects.get_or_create(
            review=review,
            user=request.user
        )

        if not created:
            helpful.delete()
            return Response({
                'message': 'Voto eliminado.',
                'helpful_count': review.helpful_count - 1
            })

        return Response({
            'message': 'Marcado como útil.',
            'helpful_count': review.helpful_count + 1
        })

    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        """Reportar una reseña"""
        review = self.get_object()
        reason = request.data.get('reason', '')

        # Aquí se puede crear un modelo de Report
        logger.info(f"Reseña {review.id} reportada por {request.user.email}: {reason}")

        return Response({'message': 'Reseña reportada. Será revisada por un moderador.'})


class ReviewByClinicView(generics.ListAPIView):
    """
    Vista para listar reseñas de una clínica.
    """
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        clinic_id = self.kwargs['clinic_id']
        return Review.objects.filter(
            clinic_id=clinic_id,
            status='approved'
        ).select_related('patient')


class ReviewByDoctorView(generics.ListAPIView):
    """
    Vista para listar reseñas de un doctor.
    """
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        doctor_id = self.kwargs['doctor_id']
        return Review.objects.filter(
            doctor_id=doctor_id,
            status='approved'
        ).select_related('patient')


class MyReviewsView(generics.ListAPIView):
    """
    Vista para listar reseñas del usuario actual.
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(patient=self.request.user)


class ReviewHelpfulView(generics.GenericAPIView):
    """
    Vista para marcar reseña como útil.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        review = Review.objects.get(id=pk)

        helpful, created = ReviewHelpful.objects.get_or_create(
            review=review,
            user=request.user
        )

        if not created:
            helpful.delete()
            return Response({'message': 'Voto eliminado.'})

        return Response({'message': 'Marcado como útil.'})


class ReviewReportView(generics.GenericAPIView):
    """
    Vista para reportar una reseña.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reason = request.data.get('reason', '')
        logger.info(f"Reseña {pk} reportada: {reason}")
        return Response({'message': 'Reseña reportada.'})


class PendingReviewsView(generics.ListAPIView):
    """
    Vista para listar reseñas pendientes (moderación).
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.user_type != 'super_admin':
            raise PermissionDenied()
        return Review.objects.filter(status='pending')


class ApproveReviewView(generics.GenericAPIView):
    """
    Vista para aprobar una reseña.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.user_type != 'super_admin':
            raise PermissionDenied()

        review = Review.objects.get(id=pk)
        review.status = 'approved'
        review.moderated_by = request.user
        review.moderated_at = timezone.now()
        review.save()

        return Response({'message': 'Reseña aprobada.'})


class RejectReviewView(generics.GenericAPIView):
    """
    Vista para rechazar una reseña.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if request.user.user_type != 'super_admin':
            raise PermissionDenied()

        review = Review.objects.get(id=pk)
        review.status = 'rejected'
        review.moderated_by = request.user
        review.moderated_at = timezone.now()
        review.moderation_notes = request.data.get('notes', '')
        review.save()

        return Response({'message': 'Reseña rechazada.'})

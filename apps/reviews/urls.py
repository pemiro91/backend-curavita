from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ReviewViewSet,
    ReviewByClinicView,
    ReviewByDoctorView,
    MyReviewsView,
    ReviewHelpfulView,
    ReviewReportView,
    PendingReviewsView,
    ApproveReviewView,
    RejectReviewView,
)

router = DefaultRouter()
router.register(r'', ReviewViewSet, basename='review')

urlpatterns = [
    path('clinic/<uuid:clinic_id>/', ReviewByClinicView.as_view(), name='reviews-by-clinic'),
    path('doctor/<uuid:doctor_id>/', ReviewByDoctorView.as_view(), name='reviews-by-doctor'),
    path('my-reviews/', MyReviewsView.as_view(), name='my-reviews'),
    path('<uuid:pk>/helpful/', ReviewHelpfulView.as_view(), name='review-helpful'),
    path('<uuid:pk>/report/', ReviewReportView.as_view(), name='review-report'),
    path('pending/', PendingReviewsView.as_view(), name='pending-reviews'),
    path('<uuid:pk>/approve/', ApproveReviewView.as_view(), name='review-approve'),
    path('<uuid:pk>/reject/', RejectReviewView.as_view(), name='review-reject'),
    path('', include(router.urls)),
]
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    NotificationViewSet,
    MyNotificationsView,
    MarkNotificationAsReadView,
    MarkAllNotificationsAsReadView,
    NotificationPreferencesView,
    UnreadNotificationsCountView,
    DeleteNotificationView,
    TestNotificationView,
)

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notification')

urlpatterns = [
    path('my-notifications/', MyNotificationsView.as_view(), name='my-notifications'),
    path('unread-count/', UnreadNotificationsCountView.as_view(), name='unread-count'),
    path('<uuid:pk>/read/', MarkNotificationAsReadView.as_view(), name='mark-notification-read'),
    path('mark-all-read/', MarkAllNotificationsAsReadView.as_view(), name='mark-all-read'),
    path('<uuid:pk>/delete/', DeleteNotificationView.as_view(), name='delete-notification'),
    path('preferences/', NotificationPreferencesView.as_view(), name='notification-preferences'),
    path('test/', TestNotificationView.as_view(), name='test-notification'),
    path('', include(router.urls)),
]
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LoyaltyAccountViewSet,
    LoyaltyTransactionListView,
    LoyaltyRedeemView,
)

router = DefaultRouter()
router.register(r'', LoyaltyAccountViewSet, basename='loyalty')

urlpatterns = [
    path('', include(router.urls)),
    path('transactions/', LoyaltyTransactionListView.as_view(), name='loyalty-transactions'),
    path('redeem/', LoyaltyRedeemView.as_view(), name='loyalty-redeem'),
]
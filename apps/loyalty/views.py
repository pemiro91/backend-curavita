import logging
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import LoyaltyAccount, LoyaltyTransaction
from .serializers import (
    LoyaltyAccountSerializer,
    LoyaltyTransactionSerializer,
    LoyaltyRedeemSerializer,
)

logger = logging.getLogger(__name__)


class LoyaltyAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver la cuenta de loyalidad del usuario autenticado.
    GET /api/v1/loyalty/me/ — retorna balance + transacciones paginadas.
    """
    serializer_class = LoyaltyAccountSerializer
    permission_classes = [IsAuthenticated]
    queryset = LoyaltyAccount.objects.all()

    def get_queryset(self):
        # Solo puede ver su propia cuenta
        return LoyaltyAccount.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        # GET /api/v1/loyalty/me/ o /api/v1/loyalty/ retorna cuenta del usuario
        account, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(account)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        # Si intentan acceder a /api/v1/loyalty/{pk}/, retornar 403 si no es su cuenta
        account = self.get_object()
        if account.user != request.user:
            return Response({'detail': 'No tienes permiso.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(account)
        return Response(serializer.data)


class LoyaltyTransactionListView(generics.ListAPIView):
    """
    GET /api/v1/loyalty/transactions/ — lista paginada de transacciones del usuario.
    """
    serializer_class = LoyaltyTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['type']
    ordering_fields = ['created_at', 'points']
    ordering = ['-created_at']

    def get_queryset(self):
        account, _ = LoyaltyAccount.objects.get_or_create(user=self.request.user)
        return LoyaltyTransaction.objects.filter(account=account)


class LoyaltyRedeemView(generics.GenericAPIView):
    """
    POST /api/v1/loyalty/redeem/ — canjear puntos por una recompensa.
    Body: { "reward_id": "...", "points_to_redeem": 50 }
    """
    serializer_class = LoyaltyRedeemSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reward_id = serializer.validated_data['reward_id']
        points = serializer.validated_data['points_to_redeem']

        account, _ = LoyaltyAccount.objects.get_or_create(user=request.user)

        # Restar puntos
        account.balance -= points
        account.save()

        # Crear transacción de canje
        transaction = LoyaltyTransaction.objects.create(
            account=account,
            type='redeem',
            points=-points,
            reason=f'Canje de recompensa: {reward_id}',
        )

        return Response({
            'message': 'Canje realizado correctamente.',
            'new_balance': account.balance,
            'transaction': LoyaltyTransactionSerializer(transaction).data,
        }, status=status.HTTP_200_OK)
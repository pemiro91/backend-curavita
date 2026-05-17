from rest_framework import serializers
from .models import LoyaltyAccount, LoyaltyTransaction
from apps.users.models import User


class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    """Serializer para transacciones de loyalidad."""
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = LoyaltyTransaction
        fields = ['id', 'type', 'points', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']


class LoyaltyAccountSerializer(serializers.ModelSerializer):
    """Serializer para cuenta de loyalidad (balance + historial paginado)."""
    user = serializers.SerializerMethodField()
    transactions = LoyaltyTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = LoyaltyAccount
        fields = ['id', 'user', 'balance', 'transactions', 'created_at', 'updated_at']
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']

    def get_user(self, obj):
        return {
            'id': str(obj.user.id),
            'email': obj.user.email,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
        }


class LoyaltyRedeemSerializer(serializers.Serializer):
    """Serializer para solicitar canje de puntos."""
    reward_id = serializers.CharField(required=True)
    points_to_redeem = serializers.IntegerField(required=True, min_value=1)

    def validate(self, attrs):
        # Validar que la cuenta tenga suficientes puntos
        user = self.context['request'].user
        try:
            account = LoyaltyAccount.objects.get(user=user)
            if account.balance < attrs['points_to_redeem']:
                raise serializers.ValidationError(
                    f"Puntos insuficientes. Balance: {account.balance}, Solicitado: {attrs['points_to_redeem']}"
                )
        except LoyaltyAccount.DoesNotExist:
            raise serializers.ValidationError("No tienes cuenta de loyalidad.")
        return attrs
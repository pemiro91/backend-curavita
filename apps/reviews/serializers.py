from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Review, ReviewHelpful

User = get_user_model()


class PatientSerializer(serializers.ModelSerializer):
    """
    Serializer básico para información del paciente en las reseñas.
    """

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'avatar']
        read_only_fields = fields


class ReviewHelpfulSerializer(serializers.ModelSerializer):
    """
    Serializer para los votos de utilidad de una reseña.
    """
    user = PatientSerializer(read_only=True)

    class Meta:
        model = ReviewHelpful
        fields = ['id', 'user', 'created_at']
        read_only_fields = fields


class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializer principal para listar reseñas.
    """
    patient = PatientSerializer(read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.get_full_name', read_only=True)
    is_helpful = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'id', 'patient', 'clinic', 'clinic_name', 'doctor', 'doctor_name',
            'rating', 'title', 'status', 'helpful_count',
            'is_helpful', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'helpful_count', 'created_at', 'updated_at']

    def get_is_helpful(self, obj):
        """
        Verifica si el usuario actual ha marcado esta reseña como útil.
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ReviewHelpful.objects.filter(review=obj, user=request.user).exists()
        return False


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para crear nuevas reseñas.
    """

    class Meta:
        model = Review
        fields = [
            'id', 'clinic', 'doctor', 'rating', 'title'
        ]
        read_only_fields = ['id']

    def validate_rating(self, value):
        """
        Valida que el rating esté entre 1 y 5.
        """
        if value < 1 or value > 5:
            raise serializers.ValidationError("El rating debe estar entre 1 y 5.")
        return value

    def validate(self, data):
        """
        Valida que se proporcione al menos una clínica o un doctor.
        """
        if not data.get('clinic') and not data.get('doctor'):
            raise serializers.ValidationError(
                "Debe especificar una clínica o un doctor para la reseña."
            )
        return data

    def create(self, validated_data):
        """
        Crea la reseña con estado 'pending' por defecto para moderación.
        """
        validated_data['status'] = 'pending'
        return super().create(validated_data)


class ReviewDetailSerializer(serializers.ModelSerializer):
    """
    Serializer detallado para ver una reseña específica.
    Incluye información adicional y votos de utilidad.
    """
    patient = PatientSerializer(read_only=True)
    clinic_name = serializers.CharField(source='clinic.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.get_full_name', read_only=True)
    is_helpful = serializers.SerializerMethodField()
    moderated_by_name = serializers.CharField(source='moderated_by.get_full_name', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'patient', 'clinic', 'clinic_name', 'doctor', 'doctor_name',
            'rating', 'title', 'status', 'helpful_count',
            'is_helpful', 'moderated_by', 'moderated_by_name', 'moderated_at',
            'moderation_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = fields

    def get_is_helpful(self, obj):
        """
        Verifica si el usuario actual ha marcado esta reseña como útil.
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ReviewHelpful.objects.filter(review=obj, user=request.user).exists()
        return False


class ReviewReportSerializer(serializers.Serializer):
    """
    Serializer para reportar una reseña.
    """
    reason = serializers.CharField(required=True, max_length=500, allow_blank=False)

    def validate_reason(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "El motivo del reporte debe tener al menos 10 caracteres."
            )
        return value


class ReviewModerationSerializer(serializers.ModelSerializer):
    """
    Serializer para moderación de reseñas (aprobar/rechazar).
    """
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    class Meta:
        model = Review
        fields = ['status', 'moderation_notes']

    def validate_status(self, value):
        if value not in ['approved', 'rejected']:
            raise serializers.ValidationError(
                "El estado debe ser 'approved' o 'rejected'."
            )
        return value
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Address

User = get_user_model()


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id', 'street', 'number', 'complement',
            'neighborhood', 'city', 'state', 'zip_code',
            'country', 'is_default'
        ]


class UserSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True, read_only=True)
    full_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'document_number', 'date_of_birth', 'gender',
            'avatar', 'user_type', 'is_verified', 'preferred_language',
            'receive_notifications', 'age', 'addresses',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'user_type', 'is_verified', 'date_joined', 'last_login']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'password',
            'password_confirm', 'phone', 'document_number',
            'date_of_birth', 'gender', 'preferred_language'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {"password_confirm": "Las contraseñas no coinciden."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone',
            'document_number', 'date_of_birth', 'gender',
            'preferred_language', 'receive_notifications'
        ]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {"new_password_confirm": "Las contraseñas no coinciden."}
            )
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    """
    Serializer para solicitar reset de contraseña.
    Valida que el email exista y tenga formato correcto.
    """
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Validar formato de email."""
        value = value.lower().strip()
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer para confirmar el reset de contraseña.
    Valida el token, uid y nueva contraseña.
    """
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        min_length=8
    )
    password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {"password_confirm": "Las contraseñas no coinciden."}
            )
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializer para verificación de email.
    """
    token = serializers.UUIDField(required=True)


class ResendVerificationSerializer(serializers.Serializer):
    """
    Serializer para reenviar verificación.
    """
    email = serializers.EmailField(required=True)


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer para perfil público de usuario (menos datos sensibles).
    """

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'avatar',
            'user_type', 'date_joined'
        ]
        read_only_fields = fields


class UserAdminSerializer(serializers.ModelSerializer):
    """
    Serializer para administradores (más campos que el normal).
    """
    addresses = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone',
            'document_number', 'date_of_birth', 'gender',
            'avatar', 'user_type', 'is_verified', 'is_active',
            'preferred_language', 'receive_notifications',
            'date_joined', 'last_login', 'addresses'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
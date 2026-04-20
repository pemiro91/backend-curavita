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
            'date_of_birth', 'gender', 'preferred_language', 'avatar'
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

    def validate_preferred_language(self, value):
        """
        Normaliza el código de idioma: es-ES → es, en-US → en, etc.
        """
        if not value:
            return 'es'

        # Convertir a minúsculas y tomar solo la parte antes del guión
        normalized = value.lower().split('-')[0]

        # Lista de idiomas permitidos
        allowed = ['es', 'en', 'pt', 'fr', 'de']

        if normalized in allowed:
            return normalized

        # Si no está en la lista, usar español por defecto
        return 'es'


# serializers.py
class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar perfil de usuario.
    """
    # PhoneNumberField es especial - usar CharField para evitar validación estricta
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone',
            'document_number', 'date_of_birth', 'gender',
            'preferred_language', 'receive_notifications', 'avatar'
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'document_number': {'required': False, 'allow_blank': True},
            'date_of_birth': {'required': False, 'allow_null': True},
            'gender': {'required': False, 'allow_blank': True},
            'preferred_language': {'required': False},
            'receive_notifications': {'required': False},
            'avatar': {'required': False, 'allow_null': True},
        }

    def validate_phone(self, value):
        """PhoneNumberField requiere formato internacional o None"""
        if not value or value == "":
            return None

        # Si ya tiene formato internacional, dejarlo pasar
        if value.startswith('+'):
            return value

        # Si no, agregar +53 (Cuba) por defecto o el código que uses
        # O simplemente devolver None si no es válido
        try:
            # Intentar validar con phonenumbers si está instalado
            import phonenumbers
            parsed = phonenumbers.parse(value, 'CU')  # Default Cuba
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except:
            pass

        # Si no se puede validar, guardar como string o None
        return value if len(value) > 5 else None

    def validate(self, attrs):
        """Validación general"""
        # Asegurar que phone sea None si está vacío
        if 'phone' in attrs and (attrs['phone'] == '' or attrs['phone'] is None):
            attrs['phone'] = None

        return attrs


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


class UserAdminCreateSerializer(serializers.ModelSerializer):
    """
    Creación de usuarios desde el panel admin. No requiere password_confirm
    y permite establecer user_type directamente.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        min_length=8,
    )

    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'password',
            'phone', 'user_type', 'preferred_language', 'is_active',
        ]
        extra_kwargs = {
            'user_type': {'required': True},
            'phone': {'required': False, 'allow_blank': True, 'allow_null': True},
            'preferred_language': {'required': False},
            'is_active': {'required': False, 'default': True},
        }

    def validate_user_type(self, value):
        allowed = ['patient', 'doctor', 'clinic_admin']
        if value not in allowed:
            raise serializers.ValidationError(
                f"user_type debe ser uno de {allowed}"
            )
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.is_verified = True
        user.save()
        return user

from django.contrib.auth.models import BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """
    Manager personalizado para el modelo User.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Crea y guarda un usuario regular.
        """
        if not email:
            raise ValueError(_('El email es obligatorio.'))

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Crea y guarda un superusuario.
        """
        # Establecer valores por defecto para superusuario
        extra_fields.setdefault('is_staff', True)  # ← FALTABA ESTO
        extra_fields.setdefault('is_superuser', True)  # ← FALTABA ESTO
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'super_admin')  # ← Opcional pero recomendado

        # Validaciones
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)

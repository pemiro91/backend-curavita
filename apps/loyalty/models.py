# loyalty/models.py
import uuid
from django.db import models
from django.conf import settings


class LoyaltyAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="loyalty_account")
    balance = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class LoyaltyTransaction(models.Model):
    TYPE_CHOICES = [("earn", "Earn"), ("redeem", "Redeem")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name="transactions")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    points = models.IntegerField()
    reason = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    # Opcional: generic FK al objeto relacionado
    content_type = models.ForeignKey("contenttypes.ContentType", on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=50, blank=True)

from django.db.models.signals import post_save
from django.dispatch import receiver

from appointments.models import Appointment
from apps.loyalty.models import LoyaltyAccount, LoyaltyTransaction


@receiver(post_save, sender=Appointment)
def award_loyalty_on_complete(sender, instance, created, **kwargs):
    if not created and instance.status == 'completed':
        try:
            account, _ = LoyaltyAccount.objects.get_or_create(user=instance.patient)
            points = 50  # configurable
            account.balance += points
            account.save()
            LoyaltyTransaction.objects.create(account=account, type='earn', points=points,
                                              reason='appointment_completed', object_id=str(instance.id))
        except Exception:
            pass

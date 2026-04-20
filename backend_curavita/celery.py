import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_curavita.settings')

app = Celery('healthhub')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'generate-daily-slots': {
        'task': 'apps.appointments.tasks.generate_daily_slots',
        'schedule': crontab(hour=0, minute=0),  # Medianoche
    },
    'cleanup-expired-slots': {
        'task': 'apps.appointments.tasks.cleanup_expired_slots',
        'schedule': crontab(hour=1, minute=0),  # 1 AM
    },
}
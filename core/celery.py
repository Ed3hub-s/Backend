import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('ed3hub')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    'send-session-reminders': {
        'task': 'notifications.tasks.send_session_reminders',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'send-assessment-reminders': {
        'task': 'notifications.tasks.send_assessment_due_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'cleanup-old-notifications': {
        'task': 'notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'send-due-newsletters': {
        'task': 'authentication.tasks.send_due_newsletters',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
}

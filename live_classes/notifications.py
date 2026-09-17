from datetime import timedelta

from .models import LiveClassReminder


REMINDER_OFFSETS = {
    '3_days': timedelta(days=3),
    '1_day': timedelta(days=1),
    '1_hour': timedelta(hours=1),
    'start': timedelta(0),
}


def schedule_live_class_reminders(live_class):
    if live_class.status != 'published':
        return
    for reminder_type, offset in REMINDER_OFFSETS.items():
        scheduled_for = live_class.starts_at - offset
        LiveClassReminder.objects.update_or_create(
            live_class=live_class,
            reminder_type=reminder_type,
            defaults={'scheduled_for': scheduled_for, 'status': 'pending', 'sent_at': None},
        )

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from notifications.utils import NotificationService

from .models import LiveClassReminder


REMINDER_COPY = {
    '3_days': ('Your Live Class is in 3 days', 'starts in 3 days.'),
    '1_day': ('Your Live Class is tomorrow', 'starts tomorrow.'),
    '1_hour': ('Your Live Class starts in 1 hour', 'starts in 1 hour.'),
    'start': ('Your Live Class is starting now', 'is starting now.'),
}


@shared_task
def send_due_live_class_reminders():
    now = timezone.now()
    due_ids = list(
        LiveClassReminder.objects.filter(status='pending', scheduled_for__lte=now)
        .values_list('id', flat=True)[:200]
    )
    sent = 0
    for reminder_id in due_ids:
        with transaction.atomic():
            reminder = LiveClassReminder.objects.select_for_update().select_related(
                'live_class', 'live_class__educator'
            ).get(pk=reminder_id)
            if reminder.status != 'pending':
                continue
            live_class = reminder.live_class
            if live_class.status not in ('published', 'live'):
                reminder.status = 'failed'
                reminder.save(update_fields=('status',))
                continue
            title, suffix = REMINDER_COPY[reminder.reminder_type]
            recipients = [live_class.educator]
            recipients.extend(
                registration.learner
                for registration in live_class.registrations.filter(access_status='active').select_related('learner')
            )
            action_url = f'/live-classes/{live_class.slug}'
            for recipient in recipients:
                NotificationService.create_notification(
                    recipient=recipient,
                    notification_type='live_class_reminder',
                    title=title,
                    message=f'{live_class.title} {suffix}',
                    live_class=live_class,
                    action_url=action_url,
                )
            reminder.status = 'sent'
            reminder.sent_at = now
            reminder.save(update_fields=('status', 'sent_at'))
            sent += 1
    return sent


@shared_task
def close_stale_attendance_visits():
    from datetime import timedelta
    from .models import LiveClassAttendance

    cutoff = timezone.now() - timedelta(hours=12)
    visits = LiveClassAttendance.objects.filter(left_at__isnull=True, joined_at__lt=cutoff)
    for visit in visits.iterator():
        visit.close(at=cutoff)


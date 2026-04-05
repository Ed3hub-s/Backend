from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from courses.models import Session
from .utils import NotificationService


@shared_task
def send_session_reminders():
    """Send session reminders - runs every 15 minutes"""
    now = timezone.now()
    
    # 24 hour reminders
    tomorrow = now + timedelta(days=1)
    sessions_24h = Session.objects.filter(
        status='scheduled',
        scheduled_date=tomorrow.date(),
        scheduled_time__hour=now.hour,
        scheduled_time__minute__range=(now.minute - 15, now.minute + 15)
    ).prefetch_related('registrations__learner')
    
    for session in sessions_24h:
        NotificationService.notify_session_reminder(session, 24)
    
    # 1 hour reminders
    one_hour_later = now + timedelta(hours=1)
    sessions_1h = Session.objects.filter(
        status='scheduled',
        scheduled_date=now.date(),
        scheduled_time__hour=one_hour_later.hour,
        scheduled_time__minute__range=(now.minute - 15, now.minute + 15)
    ).prefetch_related('registrations__learner')
    
    for session in sessions_1h:
        NotificationService.notify_session_reminder(session, 1)
    
    # 15 minute reminders
    fifteen_min_later = now + timedelta(minutes=15)
    sessions_15m = Session.objects.filter(
        status='scheduled',
        scheduled_date=now.date(),
        scheduled_time__hour=fifteen_min_later.hour,
        scheduled_time__minute__range=(fifteen_min_later.minute - 5, fifteen_min_later.minute + 5)
    ).prefetch_related('registrations__learner')
    
    for session in sessions_15m:
        for registration in session.registrations.all():
            NotificationService.create_notification(
                recipient=registration.learner,
                notification_type='session_starting',
                title='Session Starting Soon! 🔴',
                message=f'{session.title} starts in 15 minutes',
                session=session,
                action_url=session.meeting_link or f'/sessions/{session.id}',
            )


@shared_task
def send_assessment_due_reminders():
    """Send assessment due date reminders"""
    from courses.models import Assessment, Enrollment
    now = timezone.now()
    
    # 3 days before
    three_days = now.date() + timedelta(days=3)
    assessments_3d = Assessment.objects.filter(due_date=three_days)
    
    for assessment in assessments_3d:
        enrollments = Enrollment.objects.filter(course=assessment.course)
        for enrollment in enrollments:
            NotificationService.create_notification(
                recipient=enrollment.learner,
                notification_type='assessment_due',
                title='Assessment Due in 3 Days',
                message=f'{assessment.title} is due on {assessment.due_date}',
                course=assessment.course,
                action_url=f'/courses/{assessment.course.slug}/assessments/{assessment.id}',
            )
    
    # 1 day before
    tomorrow = now.date() + timedelta(days=1)
    assessments_1d = Assessment.objects.filter(due_date=tomorrow)
    
    for assessment in assessments_1d:
        enrollments = Enrollment.objects.filter(course=assessment.course)
        for enrollment in enrollments:
            NotificationService.create_notification(
                recipient=enrollment.learner,
                notification_type='assessment_due',
                title='Assessment Due Tomorrow! ⚠️',
                message=f'{assessment.title} is due tomorrow',
                course=assessment.course,
                action_url=f'/courses/{assessment.course.slug}/assessments/{assessment.id}',
            )


@shared_task
def cleanup_old_notifications():
    """Delete read notifications older than 30 days"""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    deleted_count = Notification.objects.filter(
        is_read=True,
        read_at__lt=thirty_days_ago
    ).delete()[0]
    
    return f'Deleted {deleted_count} old notifications'

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification, NotificationPreference


class NotificationService:
    """Service class for creating and sending notifications"""
    
    @staticmethod
    def create_notification(recipient, notification_type, title, message, **kwargs):
        """Create in-app notification and send real-time update"""
        # Check user preferences
        prefs, _ = NotificationPreference.objects.get_or_create(user=recipient)
        
        # Check if user wants this type of notification
        if not NotificationService._should_send_inapp(prefs, notification_type):
            return None
        
        # Create notification
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            course=kwargs.get('course'),
            session=kwargs.get('session'),
            live_class=kwargs.get('live_class'),
            message_obj=kwargs.get('message_obj'),
            action_url=kwargs.get('action_url', ''),
        )
        
        # Send real-time notification via WebSocket
        NotificationService._send_realtime(notification)
        
        # Send email if enabled
        if NotificationService._should_send_email(prefs, notification_type):
            NotificationService.send_email_notification(
                recipient=recipient,
                subject=title,
                message=message,
                notification_type=notification_type
            )
        
        return notification
    
    @staticmethod
    def _should_send_inapp(prefs, notification_type):
        """Check if user wants in-app notifications for this type"""
        type_mapping = {
            'course_enrolled': prefs.inapp_course_updates,
            'course_completed': prefs.inapp_course_updates,
            'module_completed': prefs.inapp_course_updates,
            'new_content': prefs.inapp_course_updates,
            'session_created': prefs.inapp_session_reminders,
            'session_reminder': prefs.inapp_session_reminders,
            'session_starting': prefs.inapp_session_reminders,
            'live_class_registered': prefs.inapp_session_reminders,
            'live_class_reminder': prefs.inapp_session_reminders,
            'live_class_cancelled': prefs.inapp_session_reminders,
            'new_message': prefs.inapp_messages,
            'message_reply': prefs.inapp_messages,
            'tokens_earned': prefs.inapp_tokens,
            'tokens_claimed': prefs.inapp_tokens,
            'new_review': prefs.inapp_reviews,
        }
        return type_mapping.get(notification_type, True)
    
    @staticmethod
    def _should_send_email(prefs, notification_type):
        """Check if user wants email notifications for this type"""
        type_mapping = {
            'course_enrolled': prefs.email_course_updates,
            'course_completed': prefs.email_course_updates,
            'session_reminder': prefs.email_session_reminders,
            'session_starting': prefs.email_session_reminders,
            'live_class_reminder': prefs.email_session_reminders,
            'live_class_cancelled': prefs.email_session_reminders,
            'new_message': prefs.email_messages,
            'tokens_earned': prefs.email_tokens,
            'new_review': prefs.email_reviews,
        }
        return type_mapping.get(notification_type, False)
    
    @staticmethod
    def _send_realtime(notification):
        """Send notification via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notifications_{notification.recipient.id}',
                {
                    'type': 'notification_message',
                    'notification': {
                        'id': notification.id,
                        'type': notification.notification_type,
                        'title': notification.title,
                        'message': notification.message,
                        'action_url': notification.action_url,
                        'created_at': notification.created_at.isoformat(),
                    }
                }
            )
        except Exception as e:
            print(f"Error sending real-time notification: {e}")
    
    @staticmethod
    def send_email_notification(recipient, subject, message, notification_type):
        """Send email notification"""
        try:
            send_mail(
                subject=f'[ED3Hub] {subject}',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending email notification: {e}")
    
    # Specific notification methods
    
    @staticmethod
    def notify_course_enrollment(enrollment):
        """Notify instructor of new enrollment"""
        return NotificationService.create_notification(
            recipient=enrollment.course.instructor,
            notification_type='course_enrolled',
            title='New Student Enrolled',
            message=f'{enrollment.learner.username} enrolled in {enrollment.course.title}',
            course=enrollment.course,
            action_url=f'/dashboard/courses/{enrollment.course.id}/students',
        )
    
    @staticmethod
    def notify_course_completion(enrollment):
        """Notify learner of course completion"""
        return NotificationService.create_notification(
            recipient=enrollment.learner,
            notification_type='course_completed',
            title='Course Completed! 🎉',
            message=f'Congratulations! You completed {enrollment.course.title}',
            course=enrollment.course,
            action_url=f'/courses/{enrollment.course.slug}',
        )
    
    @staticmethod
    def notify_module_completion(module_progress):
        """Notify learner of module completion"""
        return NotificationService.create_notification(
            recipient=module_progress.enrollment.learner,
            notification_type='module_completed',
            title='Module Completed! ✅',
            message=f'You completed {module_progress.module.title}',
            course=module_progress.module.course,
            action_url=f'/courses/{module_progress.module.course.slug}',
        )
    
    @staticmethod
    def notify_tokens_earned(user, amount, reason):
        """Notify learner of tokens earned"""
        return NotificationService.create_notification(
            recipient=user,
            notification_type='tokens_earned',
            title=f'Earned {amount} Tokens! 🪙',
            message=f'You earned {amount} tokens for {reason}',
            action_url='/wallet',
        )
    
    @staticmethod
    def notify_certificate_issued(certificate):
        """Notify learner of certificate issuance"""
        return NotificationService.create_notification(
            recipient=certificate.enrollment.learner,
            notification_type='certificate_issued',
            title='Certificate Ready! 🎓',
            message=f'Your certificate for {certificate.enrollment.course.title} is ready',
            course=certificate.enrollment.course,
            action_url=f'/certificates/{certificate.id}',
        )
    
    @staticmethod
    def notify_session_created(session):
        """Notify enrolled learners of new session"""
        from courses.models import Enrollment
        enrollments = Enrollment.objects.filter(course=session.course)
        
        for enrollment in enrollments:
            NotificationService.create_notification(
                recipient=enrollment.learner,
                notification_type='session_created',
                title='New Session Scheduled',
                message=f'{session.title} on {session.scheduled_date} at {session.scheduled_time}',
                session=session,
                action_url=f'/sessions/{session.id}',
            )
    
    @staticmethod
    def notify_session_reminder(session, hours_before):
        """Send session reminder to registered learners"""
        for registration in session.registrations.all():
            NotificationService.create_notification(
                recipient=registration.learner,
                notification_type='session_reminder',
                title=f'Session Starting in {hours_before}h ⏰',
                message=f'{session.title} starts at {session.scheduled_time}',
                session=session,
                action_url=f'/sessions/{session.id}',
            )
    
    @staticmethod
    def notify_session_registration(session, learner):
        """Notify instructor of session registration"""
        return NotificationService.create_notification(
            recipient=session.instructor,
            notification_type='session_registered',
            title='New Session Registration',
            message=f'{learner.username} registered for {session.title}',
            session=session,
            action_url=f'/dashboard/sessions/{session.id}',
        )
    
    @staticmethod
    def notify_new_message(message):
        """Notify recipient of new message"""
        # Get the other participant(s) in the conversation
        recipients = message.conversation.participants.exclude(id=message.sender.id)
        
        for recipient in recipients:
            NotificationService.create_notification(
                recipient=recipient,
                notification_type='new_message',
                title=f'New message from {message.sender.username}',
                message=message.text[:100] if message.text else 'Sent a file',
                message_obj=message,
                action_url=f'/chat/{message.conversation.id}',
            )
    
    @staticmethod
    def notify_new_review(review):
        """Notify instructor of new review"""
        return NotificationService.create_notification(
            recipient=review.course.instructor,
            notification_type='new_review',
            title='New Course Review',
            message=f'{review.learner.username} left a {review.rating}⭐ review on {review.course.title}',
            course=review.course,
            action_url=f'/dashboard/courses/{review.course.id}/reviews',
        )

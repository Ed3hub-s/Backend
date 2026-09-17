from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from courses.models import Course, Session
from chat.models import Message


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        # Course & Learning
        ('course_enrolled', 'Course Enrollment'),
        ('course_completed', 'Course Completed'),
        ('module_completed', 'Module Completed'),
        ('lesson_completed', 'Lesson Completed'),
        ('progress_milestone', 'Progress Milestone'),
        
        # Certificates
        ('certificate_issued', 'Certificate Issued'),
        
        # Tokens
        ('tokens_earned', 'Tokens Earned'),
        ('tokens_claimed', 'Tokens Claimed'),
        ('token_milestone', 'Token Milestone'),
        
        # Sessions
        ('session_created', 'Session Created'),
        ('session_registered', 'Session Registration'),
        ('session_reminder', 'Session Reminder'),
        ('session_starting', 'Session Starting'),
        ('session_cancelled', 'Session Cancelled'),
        ('session_rescheduled', 'Session Rescheduled'),
        ('live_class_registered', 'Live Class Registration'),
        ('live_class_reminder', 'Live Class Reminder'),
        ('live_class_cancelled', 'Live Class Cancelled'),
        
        # Chat
        ('new_message', 'New Message'),
        ('message_reply', 'Message Reply'),
        ('message_reaction', 'Message Reaction'),
        
        # Reviews
        ('new_review', 'New Review'),
        ('review_reply', 'Review Reply'),
        
        # Quizzes
        ('quiz_available', 'Quiz Available'),
        ('quiz_passed', 'Quiz Passed'),
        ('quiz_failed', 'Quiz Failed'),
        ('assessment_due', 'Assessment Due'),
        ('assessment_graded', 'Assessment Graded'),
        
        # Course Updates
        ('new_content', 'New Content'),
        ('course_updated', 'Course Updated'),
        ('announcement', 'Announcement'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Related objects
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, null=True, blank=True, on_delete=models.CASCADE)
    live_class = models.ForeignKey('live_classes.LiveClass', null=True, blank=True, on_delete=models.CASCADE)
    message_obj = models.ForeignKey(Message, null=True, blank=True, on_delete=models.CASCADE)
    
    # Action URL
    action_url = models.CharField(max_length=500, blank=True, default='')
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', '-created_at']),
        ]
    
    def __str__(self):
        return f'{self.recipient.username} - {self.title}'


class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Email notifications
    email_course_updates = models.BooleanField(default=True)
    email_session_reminders = models.BooleanField(default=True)
    email_messages = models.BooleanField(default=True)
    email_tokens = models.BooleanField(default=True)
    email_reviews = models.BooleanField(default=True)
    
    # In-app notifications
    inapp_course_updates = models.BooleanField(default=True)
    inapp_session_reminders = models.BooleanField(default=True)
    inapp_messages = models.BooleanField(default=True)
    inapp_tokens = models.BooleanField(default=True)
    inapp_reviews = models.BooleanField(default=True)
    
    # Push notifications (future)
    push_enabled = models.BooleanField(default=False)
    push_token = models.CharField(max_length=255, blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f'{self.user.username} - Notification Preferences'

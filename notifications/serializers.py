from rest_framework import serializers
from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    session_title = serializers.CharField(source='session.title', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message', 
            'course', 'course_title', 'session', 'session_title',
            'action_url', 'is_read', 'read_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'course_title', 'session_title']


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'email_course_updates', 'email_session_reminders', 
            'email_messages', 'email_tokens', 'email_reviews',
            'inapp_course_updates', 'inapp_session_reminders',
            'inapp_messages', 'inapp_tokens', 'inapp_reviews',
            'push_enabled', 'push_token'
        ]

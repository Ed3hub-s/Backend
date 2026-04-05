from django.contrib import admin
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['recipient__username', 'title', 'message']
    readonly_fields = ['created_at', 'read_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Info', {
            'fields': ('recipient', 'notification_type', 'title', 'message')
        }),
        ('Related Objects', {
            'fields': ('course', 'session', 'message_obj', 'action_url')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'created_at')
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'email_course_updates', 'email_session_reminders', 'email_messages']
    search_fields = ['user__username', 'user__email']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Email Notifications', {
            'fields': (
                'email_course_updates', 'email_session_reminders', 
                'email_messages', 'email_tokens', 'email_reviews'
            )
        }),
        ('In-App Notifications', {
            'fields': (
                'inapp_course_updates', 'inapp_session_reminders',
                'inapp_messages', 'inapp_tokens', 'inapp_reviews'
            )
        }),
        ('Push Notifications', {
            'fields': ('push_enabled', 'push_token')
        }),
    )

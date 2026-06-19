from django.conf import settings
from django.db import models


class AnalyticsEvent(models.Model):
    LANDING_PAGE_VIEW = 'landing_page_view'
    SIGNUP_COMPLETED = 'signup_completed'
    COURSE_PAGE_VIEW = 'course_page_view'
    COURSE_PURCHASE_COMPLETED = 'course_purchase_completed'
    COURSE_STARTED = 'course_started'
    COURSE_COMPLETED = 'course_completed'
    CREATOR_SIGNUP_COMPLETED = 'creator_signup_completed'
    COURSE_UPLOADED = 'course_uploaded'
    SEARCH_USED = 'search_used'
    RETURN_VISIT_7D = 'return_visit_7d'

    EVENT_CHOICES = (
        (LANDING_PAGE_VIEW, 'Landing page view'),
        (SIGNUP_COMPLETED, 'Signup completed'),
        (COURSE_PAGE_VIEW, 'Course page view'),
        (COURSE_PURCHASE_COMPLETED, 'Course purchase completed'),
        (COURSE_STARTED, 'Course started'),
        (COURSE_COMPLETED, 'Course completed'),
        (CREATOR_SIGNUP_COMPLETED, 'Creator signup completed'),
        (COURSE_UPLOADED, 'Course uploaded'),
        (SEARCH_USED, 'Search used'),
        (RETURN_VISIT_7D, 'Return visit 7d'),
    )

    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='analytics_events',
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='analytics_events',
    )
    session_key = models.CharField(max_length=40, blank=True, default='', db_index=True)
    path = models.CharField(max_length=500, blank=True, default='')
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, default='')
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = (
            models.Index(fields=('event_type', 'created_at')),
            models.Index(fields=('user', 'created_at')),
            models.Index(fields=('course', 'created_at')),
        )

    def __str__(self):
        actor = self.user.username if self.user else self.session_key or 'anonymous'
        return f'{self.event_type} - {actor}'

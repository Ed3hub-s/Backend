import csv
from datetime import timedelta

from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from unfold.admin import ModelAdmin

from .models import AnalyticsEvent


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(ModelAdmin):
    change_list_template = 'admin/analytics/analyticsevent/change_list.html'
    list_display = ('event_type', 'user', 'course', 'path', 'created_at')
    list_filter = ('event_type', 'created_at', 'course')
    search_fields = ('user__username', 'user__email', 'course__title', 'path', 'session_key')
    readonly_fields = (
        'event_type', 'user', 'course', 'session_key', 'path',
        'ip_address', 'user_agent', 'metadata', 'created_at',
    )
    date_hierarchy = 'created_at'
    actions = ('export_selected_as_csv',)

    def has_add_permission(self, request):
        return False

    def changelist_view(self, request, extra_context=None):
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        events = AnalyticsEvent.objects.all()
        recent_events = events.filter(created_at__gte=last_30_days)

        event_totals = {
            row['event_type']: row['count']
            for row in events.values('event_type').annotate(count=Count('id'))
        }
        recent_event_totals = {
            row['event_type']: row['count']
            for row in recent_events.values('event_type').annotate(count=Count('id'))
        }

        stats = []
        for value, label in AnalyticsEvent.EVENT_CHOICES:
            stats.append({
                'event_type': value,
                'label': label,
                'total': event_totals.get(value, 0),
                'last_30_days': recent_event_totals.get(value, 0),
            })

        top_courses = (
            events
            .filter(course__isnull=False)
            .values('course__title')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        extra_context = {
            **(extra_context or {}),
            'analytics_stats': stats,
            'analytics_total_events': events.count(),
            'analytics_unique_users': events.filter(user__isnull=False).values('user').distinct().count(),
            'analytics_top_courses': top_courses,
        }
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description='Export selected analytics events as CSV')
    def export_selected_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="analytics_events.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'event_type', 'user_id', 'username', 'email', 'course_id',
            'course_title', 'session_key', 'path', 'ip_address',
            'user_agent', 'metadata', 'created_at',
        ])

        for event in queryset.select_related('user', 'course').order_by('-created_at'):
            writer.writerow([
                event.event_type,
                event.user_id or '',
                event.user.username if event.user else '',
                event.user.email if event.user else '',
                event.course_id or '',
                event.course.title if event.course else '',
                event.session_key,
                event.path,
                event.ip_address or '',
                event.user_agent,
                event.metadata,
                event.created_at.isoformat(),
            ])

        return response

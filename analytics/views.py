from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Course

from .models import AnalyticsEvent
from .serializers import AnalyticsTrackSerializer
from .services import track_event


class AnalyticsTrackView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = AnalyticsTrackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        course = None
        course_id = serializer.validated_data.get('course_id')
        if course_id:
            course = Course.objects.get(id=course_id)

        track_event(
            request,
            serializer.validated_data['event_type'],
            course=course,
            metadata=serializer.validated_data.get('metadata') or {},
        )
        return Response({'detail': 'Event tracked.'}, status=status.HTTP_201_CREATED)


class AnalyticsSummaryView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self, request):
        events = AnalyticsEvent.objects.select_related('course', 'user')
        if request.user.is_staff:
            return events

        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'educator':
            return None

        return events.filter(course__instructor=request.user)

    def get(self, request):
        events = self.get_queryset(request)
        if events is None:
            return Response(
                {'detail': 'Only educators can access analytics.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        recent_events = events.filter(created_at__gte=last_30_days)

        totals = {
            row['event_type']: row['count']
            for row in events.values('event_type').annotate(count=Count('id'))
        }
        recent_totals = {
            row['event_type']: row['count']
            for row in recent_events.values('event_type').annotate(count=Count('id'))
        }

        event_breakdown = [
            {
                'event_type': value,
                'label': label,
                'total': totals.get(value, 0),
                'last_30_days': recent_totals.get(value, 0),
            }
            for value, label in AnalyticsEvent.EVENT_CHOICES
        ]

        daily_activity = [
            {'date': row['day'].isoformat(), 'count': row['count']}
            for row in (
                events
                .filter(created_at__gte=now - timedelta(days=13))
                .annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(count=Count('id'))
                .order_by('day')
            )
        ]

        top_courses = [
            {
                'course_id': row['course_id'],
                'title': row['course__title'],
                'views': row['views'],
            }
            for row in (
                events
                .filter(event_type=AnalyticsEvent.COURSE_PAGE_VIEW, course__isnull=False)
                .values('course_id', 'course__title')
                .annotate(views=Count('id'))
                .order_by('-views', 'course__title')[:5]
            )
        ]

        recent_activity = [
            {
                'id': event.id,
                'event_type': event.event_type,
                'label': event.get_event_type_display(),
                'course_title': event.course.title if event.course else '',
                'username': event.user.username if event.user else '',
                'created_at': event.created_at.isoformat(),
            }
            for event in events.order_by('-created_at')[:10]
        ]

        return Response({
            'totals': {
                'events': events.count(),
                'course_views': totals.get(AnalyticsEvent.COURSE_PAGE_VIEW, 0),
                'searches': totals.get(AnalyticsEvent.SEARCH_USED, 0),
                'purchases': totals.get(AnalyticsEvent.COURSE_PURCHASE_COMPLETED, 0),
                'course_starts': totals.get(AnalyticsEvent.COURSE_STARTED, 0),
                'course_completions': totals.get(AnalyticsEvent.COURSE_COMPLETED, 0),
                'last_30_days': recent_events.count(),
            },
            'event_breakdown': event_breakdown,
            'daily_activity': daily_activity,
            'top_courses': top_courses,
            'recent_activity': recent_activity,
        })

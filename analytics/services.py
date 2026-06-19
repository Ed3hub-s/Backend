from datetime import timedelta

from django.utils import timezone

from .models import AnalyticsEvent


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_user(request):
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return user
    return None


def track_event(request, event_type, *, user=None, course=None, metadata=None):
    if event_type not in dict(AnalyticsEvent.EVENT_CHOICES):
        raise ValueError(f'Unsupported analytics event type: {event_type}')

    user = user if user is not None else _get_user(request)
    session_key = ''
    session = getattr(request, 'session', None)
    if session is not None:
        if not session.session_key:
            session.save()
        session_key = session.session_key or ''

    return AnalyticsEvent.objects.create(
        event_type=event_type,
        user=user,
        course=course,
        session_key=session_key,
        path=request.get_full_path()[:500] if request else '',
        ip_address=get_client_ip(request) if request else None,
        user_agent=(request.META.get('HTTP_USER_AGENT', '')[:1000] if request else ''),
        metadata=metadata or {},
    )


def track_return_visit_7d(request, user):
    if not user or not user.is_authenticated:
        return None

    now = timezone.now()
    cutoff = now - timedelta(days=7)
    previous_visit = (
        AnalyticsEvent.objects
        .filter(user=user, created_at__lte=cutoff)
        .exclude(event_type=AnalyticsEvent.RETURN_VISIT_7D)
        .order_by('-created_at')
        .first()
    )
    if not previous_visit:
        return None

    already_tracked = AnalyticsEvent.objects.filter(
        user=user,
        event_type=AnalyticsEvent.RETURN_VISIT_7D,
        created_at__gte=cutoff,
    ).exists()
    if already_tracked:
        return None

    return track_event(
        request,
        AnalyticsEvent.RETURN_VISIT_7D,
        user=user,
        metadata={'previous_visit_at': previous_visit.created_at.isoformat()},
    )

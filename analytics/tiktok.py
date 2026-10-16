import hashlib
import logging
from urllib.parse import urljoin

from django.conf import settings
from django.db import transaction


logger = logging.getLogger(__name__)


def _sha256(value):
    normalized = str(value or '').strip().lower()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest() if normalized else ''


def request_match_data(request):
    """Return JSON-safe match data while the originating request is available."""
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = forwarded_for.split(',', 1)[0].strip() if forwarded_for else request.META.get('REMOTE_ADDR', '')
    query = getattr(request, 'query_params', request.GET)
    return {
        'ip': ip,
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'ttclid': query.get('ttclid', '') or request.COOKIES.get('ttclid', ''),
        'ttp': request.COOKIES.get('_ttp', ''),
    }


def page_url(path):
    return urljoin(f"{settings.FRONTEND_URL.rstrip('/')}/", str(path).lstrip('/'))


def queue_tiktok_event(*, event, event_id, user, url, properties=None, match_data=None):
    """Queue analytics after commit without ever breaking the product flow."""
    if not settings.TIKTOK_EVENTS_ACCESS_TOKEN or not settings.TIKTOK_PIXEL_ID:
        return False
    payload = {
        'event': event,
        'event_id': str(event_id),
        'email': _sha256(user.email),
        'external_id': _sha256(user.pk),
        'url': url,
        'properties': properties or {},
        'match_data': match_data or {},
    }

    def enqueue():
        try:
            from .tasks import send_tiktok_event
            send_tiktok_event.delay(payload)
        except Exception:
            logger.exception('Could not queue TikTok event %s', event_id)

    transaction.on_commit(enqueue)
    return True

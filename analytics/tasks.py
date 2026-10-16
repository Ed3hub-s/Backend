import logging
import time

import requests
from celery import shared_task
from django.conf import settings


logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={'max_retries': 3},
)
def send_tiktok_event(payload):
    """Send one event in real time; TikTok deduplicates retries by event_id."""
    token = settings.TIKTOK_EVENTS_ACCESS_TOKEN
    pixel_id = settings.TIKTOK_PIXEL_ID
    if not token or not pixel_id:
        return {'sent': False, 'reason': 'not_configured'}

    match_data = payload.get('match_data') or {}
    user = {
        key: value
        for key, value in {
            'email': payload.get('email'),
            'external_id': payload.get('external_id'),
            'ip': match_data.get('ip'),
            'user_agent': match_data.get('user_agent'),
            'ttclid': match_data.get('ttclid'),
            'ttp': match_data.get('ttp'),
        }.items()
        if value
    }
    event = {
        'event': payload['event'],
        'event_time': int(time.time()),
        'event_id': payload['event_id'],
        'user': user,
        'page': {'url': payload['url']},
    }
    if payload.get('properties'):
        event['properties'] = payload['properties']

    response = requests.post(
        settings.TIKTOK_EVENTS_API_URL,
        headers={'Access-Token': token, 'Content-Type': 'application/json'},
        json={'event_source': 'web', 'event_source_id': pixel_id, 'data': [event]},
        timeout=5,
    )
    response.raise_for_status()
    body = response.json()
    if body.get('code') != 0:
        logger.warning(
            'TikTok rejected event %s with code %s: %s',
            payload['event_id'], body.get('code'), body.get('message'),
        )
        return {'sent': False, 'code': body.get('code')}
    return {'sent': True, 'request_id': body.get('request_id')}

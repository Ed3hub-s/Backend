import logging

from django.db import connection, transaction
from django.utils import timezone

from .models import NewsletterCampaign

logger = logging.getLogger(__name__)


def claim_due_newsletter_campaigns(*, now=None, limit=None):
    """Atomically claim due scheduled campaigns before sending them."""
    now = now or timezone.now()

    with transaction.atomic():
        queryset = NewsletterCampaign.objects.filter(
            status=NewsletterCampaign.STATUS_SCHEDULED,
            scheduled_for__isnull=False,
            scheduled_for__lte=now,
        ).order_by('scheduled_for', 'id')

        select_for_update_kwargs = {}
        if connection.features.has_select_for_update_skip_locked:
            select_for_update_kwargs['skip_locked'] = True
        queryset = queryset.select_for_update(**select_for_update_kwargs)

        if limit:
            queryset = queryset[:limit]

        campaign_ids = list(queryset.values_list('id', flat=True))
        if campaign_ids:
            NewsletterCampaign.objects.filter(id__in=campaign_ids).update(
                status=NewsletterCampaign.STATUS_SENDING,
                last_error='',
                updated_at=now,
            )

    return campaign_ids


def send_claimed_newsletter_campaign(campaign_id):
    campaign = NewsletterCampaign.objects.get(id=campaign_id)
    try:
        sent, failed = campaign.send()
    except Exception as exc:
        campaign.status = NewsletterCampaign.STATUS_FAILED
        campaign.last_error = str(exc)
        campaign.save(update_fields=['status', 'last_error', 'updated_at'])
        logger.exception('Newsletter campaign %s failed before delivery finished.', campaign_id)
        return {'campaign_id': campaign_id, 'title': campaign.title, 'sent': 0, 'failed': 0, 'error': str(exc)}

    return {'campaign_id': campaign_id, 'title': campaign.title, 'sent': sent, 'failed': failed, 'error': ''}


def send_due_newsletter_campaigns(*, now=None, limit=None):
    campaign_ids = claim_due_newsletter_campaigns(now=now, limit=limit)
    return [send_claimed_newsletter_campaign(campaign_id) for campaign_id in campaign_ids]

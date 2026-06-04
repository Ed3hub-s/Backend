from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import NewsletterCampaign


@shared_task
def send_due_newsletters():
    with transaction.atomic():
        campaign_ids = list(
            NewsletterCampaign.objects
            .select_for_update(skip_locked=True)
            .filter(
                status=NewsletterCampaign.STATUS_SCHEDULED,
                scheduled_for__isnull=False,
                scheduled_for__lte=timezone.now(),
            )
            .order_by('scheduled_for')
            .values_list('id', flat=True)
        )

    results = []
    for campaign_id in campaign_ids:
        campaign = NewsletterCampaign.objects.get(id=campaign_id)
        sent, failed = campaign.send()
        results.append({'campaign_id': campaign_id, 'sent': sent, 'failed': failed})

    return results

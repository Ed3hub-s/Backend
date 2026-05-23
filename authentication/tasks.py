from celery import shared_task
from django.utils import timezone

from .models import NewsletterCampaign


@shared_task
def send_due_newsletters():
    campaign_ids = list(
        NewsletterCampaign.objects.filter(
            status=NewsletterCampaign.STATUS_SCHEDULED,
            scheduled_for__isnull=False,
            scheduled_for__lte=timezone.now(),
        ).values_list('id', flat=True)
    )

    results = []
    for campaign_id in campaign_ids:
        campaign = NewsletterCampaign.objects.get(id=campaign_id)
        sent, failed = campaign.send()
        results.append({'campaign_id': campaign_id, 'sent': sent, 'failed': failed})

    return results

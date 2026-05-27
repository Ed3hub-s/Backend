from django.core.management.base import BaseCommand
from django.utils import timezone

from authentication.models import NewsletterCampaign


class Command(BaseCommand):
    help = 'Send scheduled newsletters whose scheduled time has passed.'

    def handle(self, *args, **kwargs):
        campaigns = NewsletterCampaign.objects.filter(
            status=NewsletterCampaign.STATUS_SCHEDULED,
            scheduled_for__isnull=False,
            scheduled_for__lte=timezone.now(),
        ).order_by('scheduled_for')

        if not campaigns.exists():
            self.stdout.write('No due newsletters found.')
            return

        sent_total = 0
        failed_total = 0
        for campaign in campaigns:
            self.stdout.write(f'Sending "{campaign.title}"...')
            sent, failed = campaign.send()
            sent_total += sent
            failed_total += failed
            self.stdout.write(f'  Sent: {sent}, Failed: {failed}')

        self.stdout.write(self.style.SUCCESS(f'Done. Sent: {sent_total}, Failed: {failed_total}'))

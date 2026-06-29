import time

from django.core.management.base import BaseCommand

from authentication.newsletter_delivery import send_due_newsletter_campaigns


class Command(BaseCommand):
    help = 'Send scheduled newsletters whose scheduled time has passed. Can run once or poll without Celery/Redis.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Keep polling for due newsletters instead of running once.',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=600,
            help='Seconds between polling attempts when --loop is used. Default: 600.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Maximum number of due campaigns to claim per polling run.',
        )

    def handle(self, *args, **kwargs):
        interval = max(kwargs['interval'], 5)
        limit = kwargs.get('limit')

        while True:
            self.send_due(limit=limit)

            if not kwargs['loop']:
                return

            self.stdout.write(f'Waiting {interval} seconds before checking again...')
            time.sleep(interval)

    def send_due(self, *, limit=None):
        results = send_due_newsletter_campaigns(limit=limit)
        if not results:
            self.stdout.write('No due newsletters found.')
            return

        sent_total = sum(result['sent'] for result in results)
        failed_total = sum(result['failed'] for result in results)
        error_total = sum(1 for result in results if result['error'])

        for result in results:
            if result['error']:
                self.stdout.write(
                    self.style.ERROR(f'"{result["title"]}" failed: {result["error"]}')
                )
            else:
                self.stdout.write(
                    f'"{result["title"]}" sent. Sent: {result["sent"]}, Failed: {result["failed"]}'
                )

        message = f'Done. Campaigns: {len(results)}. Sent: {sent_total}. Failed: {failed_total}. Errors: {error_total}.'
        if failed_total or error_total:
            self.stdout.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS(message))

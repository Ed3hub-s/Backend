from django.core.management.base import BaseCommand
from django.conf import settings
from authentication.email_utils import send_smart_email, SMTP_CONFIGS, _port_open


class Command(BaseCommand):
    help = 'Test email sending with auto port detection'

    def add_arguments(self, parser):
        parser.add_argument('recipient', type=str)

    def handle(self, *args, **kwargs):
        recipient = kwargs['recipient']
        host = settings.EMAIL_HOST

        self.stdout.write(f'\nEmail host: {host}')
        self.stdout.write('Scanning ports...\n')

        for cfg in SMTP_CONFIGS:
            status = 'OPEN' if _port_open(host, cfg['port']) else 'BLOCKED'
            style = self.style.SUCCESS if status == 'OPEN' else self.style.ERROR
            self.stdout.write(style(f'  Port {cfg["port"]} ({cfg["label"]}): {status}'))

        self.stdout.write(f'\nSending test email to {recipient}...\n')
        try:
            send_smart_email(
                subject='Ed3Hub — Email Test',
                body='This is a test email from Ed3Hub. SMTP auto-detection is working.',
                recipient_list=[recipient],
                html_message='<p>This is a <strong>test email</strong> from Ed3Hub. SMTP auto-detection is working.</p>',
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Email sent successfully to {recipient}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed: {e}'))

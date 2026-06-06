from django.core.management.base import BaseCommand
from django.conf import settings
from authentication.email_utils import send_smart_email


class Command(BaseCommand):
    help = 'Test SMTP email sending'

    def add_arguments(self, parser):
        parser.add_argument('recipient', type=str)

    def handle(self, *args, **kwargs):
        recipient = kwargs['recipient']

        self.stdout.write('Method: SMTP')
        self.stdout.write(f'Host:   {settings.EMAIL_HOST}:{settings.EMAIL_PORT}')
        self.stdout.write(f'From:   {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'To:     {recipient}\n')

        try:
            send_smart_email(
                subject='Ed3Hub - Email Test',
                body='This is a test email from Ed3Hub.',
                recipient_list=[recipient],
                html_message='<p>This is a <strong>test email</strong> from <strong>Ed3Hub</strong>. Email delivery is working correctly.</p>',
            )
            self.stdout.write(self.style.SUCCESS('Email sent successfully!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed: {e}'))

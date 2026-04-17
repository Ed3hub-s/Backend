import os
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Send a test email to verify SMTP configuration'

    def add_arguments(self, parser):
        parser.add_argument('recipient', type=str, help='Email address to send the test email to')

    def handle(self, *args, **kwargs):
        recipient = kwargs['recipient']

        self.stdout.write(f'\nEmail settings:')
        self.stdout.write(f'  HOST:     {settings.EMAIL_HOST}')
        self.stdout.write(f'  PORT:     {settings.EMAIL_PORT}')
        self.stdout.write(f'  USER:     {settings.EMAIL_HOST_USER}')
        self.stdout.write(f'  USE_TLS:  {settings.EMAIL_USE_TLS}')
        self.stdout.write(f'  USE_SSL:  {settings.EMAIL_USE_SSL}')
        self.stdout.write(f'  FROM:     {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'\nSending test email to {recipient} ...\n')

        try:
            send_mail(
                subject='Ed3Hub — Email Test',
                message='This is a test email from Ed3Hub. If you received this, your SMTP configuration is working correctly.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Email sent successfully to {recipient}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to send email: {e}'))

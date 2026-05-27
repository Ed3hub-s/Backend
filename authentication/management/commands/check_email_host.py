import socket

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Check the configured email host and common SMTP ports.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=5)

    def handle(self, *args, **kwargs):
        host = settings.EMAIL_HOST
        timeout = kwargs['timeout']
        ports = (
            (587, 'STARTTLS'),
            (465, 'SSL'),
            (2525, 'STARTTLS alternate'),
            (25, 'plain SMTP'),
        )

        self.stdout.write(f'Email host: {host}')
        self.stdout.write(f'From:       {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write('')

        for port, label in ports:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    self.stdout.write(self.style.SUCCESS(f'Port {port} ({label}): open'))
            except OSError as exc:
                self.stdout.write(self.style.WARNING(f'Port {port} ({label}): unavailable ({exc})'))

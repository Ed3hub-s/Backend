import os
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Create or repair the environment-configured superuser'

    def handle(self, *args, **kwargs):
        username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@ed3hub.com')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD')

        if not password:
            self.stdout.write(self.style.WARNING(
                'DJANGO_SUPERUSER_PASSWORD not set — skipping superuser creation.'
            ))
            return

        with transaction.atomic():
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User.objects.filter(email__iexact=email).first()

            created = user is None
            if created:
                user = User(username=username)
            elif user.username != username:
                if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                    self.stderr.write(self.style.ERROR(
                        f'Cannot repair superuser: username "{username}" is already in use.'
                    ))
                    return
                user.username = username

            user.email = email
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()

        action = 'created' if created else 'repaired'
        self.stdout.write(self.style.SUCCESS(
            f'Superuser "{username}" {action} successfully.'
        ))

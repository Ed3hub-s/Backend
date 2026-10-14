from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase


class CreateSuperuserEnvTests(TestCase):
    env = {
        'DJANGO_SUPERUSER_USERNAME': 'admin',
        'DJANGO_SUPERUSER_EMAIL': 'admin@ed3hub.com',
        'DJANGO_SUPERUSER_PASSWORD': 'test-password-123',
    }

    @patch.dict('os.environ', env, clear=False)
    def test_creates_superuser(self):
        call_command('create_superuser_env')

        user = User.objects.get(username='admin')
        self.assertEqual(user.email, 'admin@ed3hub.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('test-password-123'))

    @patch.dict('os.environ', env, clear=False)
    def test_repairs_existing_account(self):
        user = User.objects.create_user(
            username='admin',
            email='old@example.com',
            password='old-password',
            is_active=False,
            is_staff=False,
            is_superuser=False,
        )

        call_command('create_superuser_env')

        user.refresh_from_db()
        self.assertEqual(user.email, 'admin@ed3hub.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('test-password-123'))

    @patch.dict('os.environ', env, clear=False)
    def test_repairs_account_found_by_email(self):
        user = User.objects.create_user(
            username='legacy-admin',
            email='admin@ed3hub.com',
            password='old-password',
        )

        call_command('create_superuser_env')

        user.refresh_from_db()
        self.assertEqual(user.username, 'admin')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('test-password-123'))

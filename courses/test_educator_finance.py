from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import UserProfile
from .models import EducatorWallet, PlatformSettings, WithdrawalRequest


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='notifications@ed3hub.com',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class EducatorWithdrawalNotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.educator = User.objects.create_user(
            username='educator', email='educator@example.com', password='pass',
        )
        UserProfile.objects.update_or_create(user=self.educator, defaults={'role': 'educator'})
        self.wallet = EducatorWallet.objects.create(
            educator=self.educator, balance=Decimal('5000.00'), total_earned=Decimal('5000.00'),
        )
        PlatformSettings.objects.update_or_create(
            pk=1, defaults={'withdrawal_notification_email': 'finance@example.com'},
        )
        self.client.force_authenticate(self.educator)

    def test_withdrawal_uses_admin_configured_notification_recipient(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/courses/educator/withdraw/', {
                'amount': '1200.00',
                'bank_name': 'Example Bank',
                'account_number': '0123456789',
                'account_name': 'Test Educator',
            }, format='json')

        self.assertEqual(response.status_code, 201)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('3800.00'))
        self.assertEqual(WithdrawalRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['finance@example.com'])
        self.assertIn('Test Educator', mail.outbox[0].body)

    def test_blank_notification_recipient_does_not_block_withdrawal(self):
        PlatformSettings.objects.filter(pk=1).update(withdrawal_notification_email='')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/courses/educator/withdraw/', {
                'amount': '100.00',
                'bank_name': 'Example Bank',
                'account_number': '0123456789',
                'account_name': 'Test Educator',
            }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 0)

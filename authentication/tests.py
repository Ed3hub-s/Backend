from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AffiliateMarketer, AffiliateReferral, OTPCode, UserProfile


class WelcomeEmailTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('authentication.utils.send_smart_email', return_value=True)
    def test_learner_receives_welcome_email_after_otp_verification(self, send_email):
        user = User.objects.create_user(
            username='ada',
            email='ada@example.com',
            password='StrongPass123',
            is_active=False,
        )
        UserProfile.objects.create(user=user, role='learner')
        OTPCode.objects.create(
            email=user.email,
            code='123456',
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = self.client.post('/api/auth/verify-otp/', {'email': user.email, 'code': '123456'}, format='json')

        self.assertEqual(response.status_code, 200)
        send_email.assert_called_once()
        _, kwargs = send_email.call_args
        self.assertEqual(kwargs['subject'], "Welcome to Ed3hub let's get to work")
        self.assertEqual(kwargs['recipient_list'], [user.email])
        self.assertIn('Welcome to Ed3hub', kwargs['html_message'])
        self.assertIn('Curated courses and bootcamps designed for real results', kwargs['html_message'])

    @patch('authentication.utils.send_smart_email', return_value=True)
    @patch('authentication.views.requests.get')
    def test_new_google_educator_receives_creator_welcome_email(self, google_get, send_email):
        google_get.return_value = Mock(
            status_code=200,
            json=lambda: {
                'email': 'creator@example.com',
                'name': 'Grace Hopper',
            },
        )

        response = self.client.post(
            '/api/auth/google/',
            {'access_token': 'google-token', 'role': 'educator'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_new_user'])
        send_email.assert_called_once()
        _, kwargs = send_email.call_args
        self.assertEqual(kwargs['recipient_list'], ['creator@example.com'])
        self.assertIn('you just joined Ed3hub as a course creator', kwargs['html_message'])
        self.assertIn('/dashboard', kwargs['html_message'])


class AffiliateSignupFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.marketer = User.objects.create_user(
            username='marketer',
            email='marketer@example.com',
            password='StrongPass123',
            is_active=True,
        )
        UserProfile.objects.create(user=self.marketer, role='marketer')
        self.affiliate = AffiliateMarketer.objects.get(user=self.marketer)

    @patch('authentication.views.create_and_send_otp')
    def test_referred_signup_is_listed_on_marketer_dashboard(self, send_otp):
        response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'referred',
                'email': 'referred@example.com',
                'password': 'StrongPass123',
                'role': 'learner',
                'referral_code': self.affiliate.referral_code,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        referral = AffiliateReferral.objects.get(referred_user__username='referred')
        self.assertEqual(referral.marketer, self.marketer)
        self.assertEqual(referral.referral_code, self.affiliate.referral_code)

        self.client.force_authenticate(self.marketer)
        dashboard = self.client.get('/api/auth/marketer/dashboard/')

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data['total_referred_users'], 1)
        self.assertEqual(dashboard.data['referrals'][0]['username'], 'referred')
        self.assertFalse(dashboard.data['referrals'][0]['signup_bonus_paid'])

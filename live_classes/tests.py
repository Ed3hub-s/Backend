from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from authentication.models import UserProfile

from .models import LiveClass, LiveClassPayment, LiveClassRegistration


class LiveClassAPITests(APITestCase):
    def setUp(self):
        self.educator = User.objects.create_user('educator', 'teacher@example.com', 'pass12345')
        UserProfile.objects.update_or_create(user=self.educator, defaults={'role': 'educator'})
        self.learner = User.objects.create_user('learner', 'learner@example.com', 'pass12345')
        UserProfile.objects.update_or_create(user=self.learner, defaults={'role': 'learner'})
        self.other = User.objects.create_user('other', 'other@example.com', 'pass12345')
        UserProfile.objects.update_or_create(user=self.other, defaults={'role': 'learner'})

    def make_class(self, access_type='free', price=0, minutes_from_now=120):
        starts = timezone.localtime() + timedelta(minutes=minutes_from_now)
        return LiveClass.objects.create(
            educator=self.educator,
            title=f'{access_type.title()} workshop',
            description='A practical live workshop.',
            category='Technology',
            level='beginner',
            scheduled_date=starts.date(),
            scheduled_time=starts.time().replace(microsecond=0),
            duration_minutes=60,
            capacity=2,
            learning_objectives='Build one working project',
            access_type=access_type,
            price=price,
            currency='NGN',
            status='published',
        )

    def test_marketplace_is_public(self):
        live_class = self.make_class()
        response = self.client.get('/api/live-classes/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['slug'], live_class.slug)
        self.assertEqual(response.data[0]['available_spaces'], 2)

    def test_free_registration_activates_access(self):
        live_class = self.make_class()
        self.client.force_authenticate(self.learner)
        response = self.client.post(f'/api/live-classes/{live_class.slug}/register/')
        self.assertEqual(response.status_code, 201)
        registration = LiveClassRegistration.objects.get(live_class=live_class, learner=self.learner)
        self.assertEqual(registration.access_status, 'active')
        self.assertEqual(registration.registration_status, 'confirmed')

    @override_settings(PAYSTACK_SECRET_KEY='test-secret')
    @patch('live_classes.services.requests.post')
    def test_paid_registration_stays_pending_until_verified(self, mocked_post):
        mocked_post.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={'status': True, 'data': {'authorization_url': 'https://checkout.test', 'reference': 'ref'}}),
        )
        live_class = self.make_class('paid', Decimal('2500.00'))
        self.client.force_authenticate(self.learner)
        response = self.client.post(f'/api/live-classes/{live_class.slug}/register/')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['checkout']['authorization_url'], 'https://checkout.test')
        registration = LiveClassRegistration.objects.get(live_class=live_class, learner=self.learner)
        self.assertEqual(registration.access_status, 'pending')
        self.assertEqual(registration.payment.status, 'pending')

    @override_settings(PAYSTACK_SECRET_KEY='test-secret')
    @patch('live_classes.services.requests.get')
    def test_successful_payment_grants_access(self, mocked_get):
        live_class = self.make_class('paid', Decimal('2500.00'))
        payment = LiveClassPayment.objects.create(
            user=self.learner,
            amount=live_class.price,
            currency='NGN',
            transaction_reference='LC-payment-reference',
        )
        LiveClassRegistration.objects.create(live_class=live_class, learner=self.learner, payment=payment)
        mocked_get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={'status': True, 'data': {'status': 'success', 'amount': 250000}}),
        )
        self.client.force_authenticate(self.learner)
        response = self.client.post(
            f'/api/live-classes/{live_class.slug}/verify-payment/',
            {'reference': payment.transaction_reference},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['access_status'], 'active')

    def test_unregistered_user_cannot_join(self):
        live_class = self.make_class(minutes_from_now=5)
        self.client.force_authenticate(self.other)
        response = self.client.post(f'/api/live-classes/{live_class.slug}/join/')
        self.assertEqual(response.status_code, 403)

    @patch('live_classes.views.CloudflareRealtimeKitV1')
    def test_active_learner_receives_provider_token(self, provider_class):
        live_class = self.make_class(minutes_from_now=5)
        LiveClassRegistration.objects.create(
            live_class=live_class,
            learner=self.learner,
            registration_status='confirmed',
            access_status='active',
            access_granted_at=timezone.now(),
        )
        provider = provider_class.return_value
        provider.participant_token.return_value = ('participant-id', 'short-lived-token')
        self.client.force_authenticate(self.learner)
        response = self.client.post(f'/api/live-classes/{live_class.slug}/join/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['auth_token'], 'short-lived-token')
        self.assertEqual(response.data['role'], 'learner')

    def test_learner_cannot_create_live_class(self):
        self.client.force_authenticate(self.learner)
        response = self.client.post('/api/live-classes/educator/', {}, format='json')
        self.assertEqual(response.status_code, 403)

    @override_settings(PAYSTACK_SECRET_KEY='test-secret')
    @patch('live_classes.services.requests.get')
    def test_signed_paystack_webhook_activates_pending_access(self, mocked_get):
        live_class = self.make_class('paid', Decimal('2500.00'))
        payment = LiveClassPayment.objects.create(
            user=self.learner,
            amount=live_class.price,
            currency='NGN',
            transaction_reference='LC-webhook-reference',
        )
        registration = LiveClassRegistration.objects.create(
            live_class=live_class,
            learner=self.learner,
            payment=payment,
        )
        mocked_get.return_value = Mock(
            raise_for_status=Mock(),
            json=Mock(return_value={'status': True, 'data': {'status': 'success', 'amount': 250000}}),
        )
        payload = json.dumps({'event': 'charge.success', 'data': {'reference': payment.transaction_reference}}).encode()
        signature = hmac.new(b'test-secret', payload, hashlib.sha512).hexdigest()
        response = self.client.post(
            '/api/live-classes/webhooks/paystack/',
            data=payload,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        self.assertEqual(response.status_code, 200)
        registration.refresh_from_db()
        self.assertEqual(registration.access_status, 'active')

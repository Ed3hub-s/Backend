import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import LiveClass, LiveClassPayment, LiveClassRecording, LiveClassRegistration


@override_settings(PAYSTACK_SECRET_KEY='test-secret', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PaidClassTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user('teacher', 'teacher@example.com')
        self.student = User.objects.create_user('student', 'student@example.com')
        starts = timezone.localtime() + timedelta(minutes=5)
        self.live_class = LiveClass.objects.create(
            educator=self.teacher, title='Paid workshop', description='Workshop',
            category='Technology', level='beginner', scheduled_date=starts.date(),
            scheduled_time=starts.time(), duration_minutes=60, capacity=10,
            learning_objectives='Learn', access_type='paid', price='2500.00', status='published',
        )
        self.payment = LiveClassPayment.objects.create(
            user=self.student, amount='2500.00', currency='NGN', transaction_reference='LC-test',
            metadata={'customer_email': self.student.email},
        )
        self.registration = LiveClassRegistration.objects.create(
            live_class=self.live_class, learner=self.student, payment=self.payment,
        )
        self.client.force_authenticate(self.student)
        self.base = f'/api/live-classes/{self.live_class.slug}'

    def verification(self, **changes):
        data = {'status': 'success', 'amount': 250000, 'currency': 'NGN',
                'reference': self.payment.transaction_reference, 'customer': {'email': self.student.email}}
        data.update(changes)
        return Mock(raise_for_status=Mock(), json=Mock(return_value={'status': True, 'data': data}))

    def webhook(self, event, data, signature=None):
        payload = json.dumps({'event': event, 'data': data}).encode()
        signature = signature or hmac.new(b'test-secret', payload, hashlib.sha512).hexdigest()
        return self.client.post('/api/live-classes/webhooks/paystack/', payload,
                                content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature)

    @patch('live_classes.services.requests.get')
    def test_verification_rejects_mismatched_payment_details(self, get):
        for changes in ({'currency': 'USD'}, {'reference': 'somebody-elses-payment'},
                        {'amount': 1}, {'amount': 'invalid'}, {'status': 'pending'},
                        {'customer': {'email': 'other@example.com'}}):
            with self.subTest(changes=changes):
                get.return_value = self.verification(**changes)
                response = self.client.post(self.base + '/verify-payment/', {}, format='json')
                self.assertEqual(response.status_code, 400)
                self.registration.refresh_from_db()
                self.assertEqual(self.registration.access_status, 'pending')

    @patch('live_classes.services.requests.get')
    def test_invoice_amount_survives_class_price_change_and_duplicate_callback(self, get):
        self.live_class.price = '5000.00'
        self.live_class.save()
        get.return_value = self.verification()
        for _ in range(2):
            response = self.client.post(self.base + '/verify-payment/', {}, format='json')
            self.assertEqual(response.status_code, 200)
        self.registration.refresh_from_db()
        self.assertEqual(str(self.registration.amount_paid), '2500.00')
        self.assertEqual(self.registration.access_status, 'active')
        get.assert_called_once()

    @patch('live_classes.services.requests.post')
    def test_resume_checkout_reuses_saved_link_without_reinitializing(self, post):
        post.return_value = Mock(raise_for_status=Mock(), json=Mock(return_value={
            'status': True, 'data': {'reference': 'LC-test', 'authorization_url': 'https://checkout.paystack.com/test'},
        }))
        first = self.client.post(self.base + '/register/')
        second = self.client.post(self.base + '/register/')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.data['checkout'], first.data['checkout'])
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs['json']['amount'], 250000)

    @patch('live_classes.services.requests.post')
    def test_cancelled_class_cannot_resume_checkout(self, post):
        self.live_class.status = 'cancelled'
        self.live_class.save()
        self.assertEqual(self.client.post(self.base + '/register/').status_code, 400)
        post.assert_not_called()

    @patch('live_classes.views.CloudflareRealtimeKitV1')
    def test_unpaid_student_cannot_join(self, provider):
        self.assertEqual(self.client.post(self.base + '/join/').status_code, 403)
        provider.assert_not_called()

    @patch('live_classes.services.requests.get')
    def test_other_users_reference_is_rejected_before_provider_call(self, get):
        response = self.client.post(self.base + '/verify-payment/', {'reference': 'other'}, format='json')
        self.assertEqual(response.status_code, 400)
        get.assert_not_called()

    @patch('live_classes.services.requests.get')
    def test_webhook_verifies_without_browser_callback(self, get):
        get.return_value = self.verification()
        for _ in range(2):
            self.assertEqual(self.webhook('charge.success', {'reference': 'LC-test'}).status_code, 200)
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.access_status, 'active')
        get.assert_called_once()

    def test_forged_webhook_rejected(self):
        self.assertEqual(self.webhook('charge.success', {'reference': 'LC-test'}, 'forged').status_code, 401)

    @patch('live_classes.services.requests.get')
    def test_refund_cannot_be_undone_by_late_success_callback(self, get):
        response = self.webhook('refund.processed', {
            'transaction_reference': 'LC-test', 'amount': '250000', 'currency': 'NGN',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.webhook('charge.success', {'reference': 'LC-test'}).status_code, 200)
        self.assertEqual(self.client.post(self.base + '/verify-payment/', {}, format='json').status_code, 200)
        self.registration.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.registration.access_status, 'refunded')
        self.assertEqual(self.payment.status, 'refunded')
        get.assert_not_called()

    def test_processing_failed_and_partial_refunds_do_not_remove_access(self):
        self.registration.access_status = 'active'
        self.registration.save()
        for event, amount in [('refund.processing', 250000), ('refund.failed', 250000), ('refund.processed', 100)]:
            self.assertEqual(self.webhook(event, {
                'transaction_reference': 'LC-test', 'amount': amount, 'currency': 'NGN',
            }).status_code, 200)
            self.registration.refresh_from_db()
            self.assertEqual(self.registration.access_status, 'active')

    @patch('live_classes.services.requests.get')
    def test_revoked_registration_cannot_be_reactivated(self, get):
        self.registration.access_status = 'revoked'
        self.registration.save()
        self.client.post(self.base + '/verify-payment/', {}, format='json')
        self.registration.refresh_from_db()
        self.assertEqual(self.registration.access_status, 'revoked')
        get.assert_not_called()

    @patch('live_classes.services.requests.get')
    def test_verification_rejects_payment_owned_by_another_learner(self, get):
        self.payment.user = self.teacher
        self.payment.save(update_fields=['user'])
        self.assertEqual(self.client.post(self.base + '/verify-payment/', {}, format='json').status_code, 400)
        get.assert_not_called()

    @patch('live_classes.views.CloudflareRealtimeKitV1')
    def test_every_join_and_recording_request_rechecks_database(self, provider):
        self.payment.status = 'successful'
        self.payment.save()
        self.registration.registration_status = 'confirmed'
        self.registration.access_status = 'active'
        self.registration.save()
        provider.return_value.participant_token.return_value = ('participant', 'token')
        provider.return_value.get_recording.return_value = {'download_url': 'https://example.com/recording.mp4'}
        recording = LiveClassRecording.objects.create(
            live_class=self.live_class, provider_recording_id='replay', status='available',
        )
        playback = f'/api/live-classes/recordings/{recording.pk}/access/'
        self.assertEqual(self.client.post(self.base + '/join/').status_code, 200)
        self.assertEqual(self.client.get(playback).status_code, 200)
        # Change only the payment: a stale active registration must not grant access.
        for changes in ({'status': 'pending'}, {'status': 'failed'}, {'status': 'refunded'},
                        {'status': 'successful', 'user': self.teacher}):
            with self.subTest(changes=changes):
                LiveClassPayment.objects.filter(pk=self.payment.pk).update(**changes)
                provider.reset_mock()
                self.assertEqual(self.client.post(self.base + '/join/').status_code, 403)
                self.assertEqual(self.client.get(playback).status_code, 403)
                self.assertEqual(self.client.get(self.base + '/recordings/').status_code, 403)
                provider.assert_not_called()

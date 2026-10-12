import hashlib
import hmac
import json
from decimal import Decimal
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.db.models import Sum
from rest_framework.test import APITestCase

from authentication.models import UserProfile
from .models import LiveClass, LiveClassBundle, LiveClassPayment, LiveClassRecording, LiveClassRegistration


@override_settings(PAYSTACK_SECRET_KEY='test-secret', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BundlePaymentTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user('teacher', 'teacher@example.com')
        UserProfile.objects.update_or_create(user=self.teacher, defaults={'role': 'educator'})
        self.learner = User.objects.create_user('learner', 'learner@example.com')
        self.classes = []
        for number in range(2):
            starts = timezone.localtime() + timedelta(minutes=5 + number)
            self.classes.append(LiveClass.objects.create(
                educator=self.teacher, title=f'Data session {number}', description='Learn data',
                category='Data', level='beginner', scheduled_date=starts.date(), scheduled_time=starts.time(),
                duration_minutes=60, capacity=10, learning_objectives='Learn', access_type='paid', price=2500, status='published',
            ))
        self.client.force_authenticate(self.teacher)

    def bundle(self):
        response = self.client.post('/api/live-classes/educator/bundles/', {
            'title': 'Data programme', 'description': 'All sessions', 'price': '4000.00', 'currency': 'NGN',
            'class_ids': [item.pk for item in self.classes],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        for item in self.classes:
            item.refresh_from_db()
        return LiveClassBundle.objects.get(pk=response.data['id'])

    def initialize(self, *args, **kwargs):
        reference = kwargs['json']['reference']
        return Mock(raise_for_status=Mock(), json=Mock(return_value={'status': True, 'data': {'reference': reference, 'authorization_url': 'https://checkout.paystack.com/bundle'}}))

    @patch('live_classes.services.requests.post')
    @patch('live_classes.services.requests.get')
    @patch('live_classes.views.CloudflareRealtimeKitV1')
    def test_one_payment_unlocks_all_sessions_and_refund_blocks_every_entry(self, provider, get, post):
        self.bundle()
        self.client.force_authenticate(self.learner)
        post.side_effect = self.initialize
        first, second = self.classes
        response = self.client.post(f'/api/live-classes/{first.slug}/register/')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(LiveClassPayment.objects.count(), 1)
        self.assertEqual(LiveClassRegistration.objects.count(), 2)
        payment = LiveClassPayment.objects.get()
        self.assertEqual(payment.amount, 4000)
        self.assertEqual(post.call_args.kwargs['json']['amount'], 400000)
        self.assertEqual(self.client.post(f'/api/live-classes/{second.slug}/register/').status_code, 200)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(self.client.post(f'/api/live-classes/{first.slug}/join/').status_code, 403)
        provider.assert_not_called()
        get.return_value = Mock(raise_for_status=Mock(), json=Mock(return_value={'status': True, 'data': {
            'status': 'success', 'reference': payment.transaction_reference, 'amount': 400000,
            'currency': 'NGN', 'customer': {'email': self.learner.email},
        }}))
        self.assertEqual(self.client.post(f'/api/live-classes/{second.slug}/verify-payment/').status_code, 200)
        self.assertEqual(LiveClassRegistration.objects.filter(access_status='active').count(), 2)
        provider.return_value.participant_token.return_value = ('participant', 'token')
        for item in self.classes:
            self.assertEqual(self.client.post(f'/api/live-classes/{item.slug}/join/').status_code, 200)
        payload = json.dumps({'event': 'refund.processed', 'data': {'transaction_reference': payment.transaction_reference, 'amount': 400000, 'currency': 'NGN'}}).encode()
        signature = hmac.new(b'test-secret', payload, hashlib.sha512).hexdigest()
        self.assertEqual(self.client.post('/api/live-classes/webhooks/paystack/', payload, content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature).status_code, 200)
        for item in self.classes:
            self.assertEqual(self.client.post(f'/api/live-classes/{item.slug}/join/').status_code, 403)
        self.assertEqual(LiveClassRegistration.objects.filter(access_status='refunded').count(), 2)

    def test_cannot_bundle_another_educators_class_or_registered_class(self):
        other = User.objects.create_user('other')
        self.classes[0].educator = other
        self.classes[0].save()
        data = {'title': 'Bundle', 'description': 'Bundle', 'price': '4000', 'class_ids': [item.pk for item in self.classes]}
        self.assertEqual(self.client.post('/api/live-classes/educator/bundles/', data, format='json').status_code, 400)
        self.classes[0].educator = self.teacher
        self.classes[0].save()
        LiveClassRegistration.objects.create(live_class=self.classes[0], learner=self.learner)
        self.assertEqual(self.client.post('/api/live-classes/educator/bundles/', data, format='json').status_code, 400)
        self.assertFalse(LiveClassBundle.objects.exists())

    @patch('live_classes.services.requests.post')
    def test_full_session_prevents_partial_bundle_booking(self, post):
        self.bundle()
        self.classes[0].capacity = 1
        self.classes[0].save()
        other = User.objects.create_user('other')
        LiveClassRegistration.objects.create(live_class=self.classes[0], learner=other)
        self.client.force_authenticate(self.learner)
        self.assertEqual(self.client.post(f'/api/live-classes/{self.classes[1].slug}/register/').status_code, 400)
        self.assertFalse(LiveClassRegistration.objects.filter(learner=self.learner).exists())
        self.assertFalse(LiveClassPayment.objects.exists())
        post.assert_not_called()

    @patch('live_classes.views.CloudflareRealtimeKitV1')
    def test_active_flag_without_successful_payment_cannot_join_or_watch_recordings(self, provider):
        item = self.classes[0]
        registration = LiveClassRegistration.objects.create(live_class=item, learner=self.learner, registration_status='confirmed', access_status='active')
        recording = LiveClassRecording.objects.create(live_class=item, provider_recording_id='recording', status='available')
        self.client.force_authenticate(self.learner)
        for payment_status in (None, 'pending', 'refunded', 'failed'):
            if payment_status:
                payment = LiveClassPayment.objects.create(user=self.learner, amount=2500, transaction_reference=f'test-{payment_status}', status=payment_status)
                registration.payment = payment
                registration.save()
            self.assertEqual(self.client.post(f'/api/live-classes/{item.slug}/join/').status_code, 403)
            self.assertEqual(self.client.get(f'/api/live-classes/recordings/{recording.pk}/access/').status_code, 403)
        provider.assert_not_called()

    def test_bundle_session_cannot_be_deleted_or_repriced(self):
        self.bundle()
        item = self.classes[0]
        self.assertEqual(self.client.delete(f'/api/live-classes/educator/{item.slug}/').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/live-classes/educator/{item.slug}/', {'price': '1'}, format='json').status_code, 400)

    def test_learner_cannot_create_bundle(self):
        self.client.force_authenticate(self.learner)
        self.assertEqual(self.client.post('/api/live-classes/educator/bundles/', {}, format='json').status_code, 403)

    @patch('live_classes.services.requests.post')
    @patch('live_classes.services.requests.get')
    def test_webhook_alone_activates_entire_bundle_and_allocates_invoice_once(self, get, post):
        bundle = self.bundle()
        bundle.price = Decimal('4000.01')
        bundle.save()
        self.client.force_authenticate(self.learner)
        post.side_effect = self.initialize
        self.client.post(f'/api/live-classes/{self.classes[1].slug}/register/')
        payment = LiveClassPayment.objects.get()
        get.return_value = Mock(raise_for_status=Mock(), json=Mock(return_value={'status': True, 'data': {
            'status': 'success', 'reference': payment.transaction_reference, 'amount': 400001,
            'currency': 'NGN', 'customer': {'email': self.learner.email},
        }}))
        payload = json.dumps({'event': 'charge.success', 'data': {'reference': payment.transaction_reference}}).encode()
        signature = hmac.new(b'test-secret', payload, hashlib.sha512).hexdigest()
        self.client.force_authenticate(None)
        for _ in range(2):
            response = self.client.post('/api/live-classes/webhooks/paystack/', payload,
                                        content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature)
            self.assertEqual(response.status_code, 200)
        get.assert_called_once()
        self.assertEqual(payment.registrations.filter(access_status='active').count(), 2)
        self.assertEqual(payment.registrations.aggregate(total=Sum('amount_paid'))['total'], payment.amount)
        self.assertEqual(list(payment.registrations.order_by('live_class_id').values_list('amount_paid', flat=True)),
                         [Decimal('2000.01'), Decimal('2000.00')])

    def test_bundle_detail_lists_all_sessions_and_only_eligible_classes_can_be_selected(self):
        response = self.client.get('/api/live-classes/educator/')
        self.assertTrue(all(item['eligible_for_bundle'] for item in response.data))
        self.bundle()
        response = self.client.get(f'/api/live-classes/{self.classes[0].slug}/')
        self.assertEqual([item['id'] for item in response.data['bundle_sessions']], [item.pk for item in self.classes])
        self.assertFalse(response.data['eligible_for_bundle'])

    def test_pending_registrations_make_class_ineligible_for_bundling(self):
        LiveClassRegistration.objects.create(live_class=self.classes[0], learner=self.learner)
        response = self.client.get('/api/live-classes/educator/')
        by_id = {item['id']: item for item in response.data}
        self.assertFalse(by_id[self.classes[0].pk]['eligible_for_bundle'])
        self.assertTrue(by_id[self.classes[1].pk]['eligible_for_bundle'])

    def test_educator_can_create_program_and_all_sessions_together(self):
        starts = timezone.localtime() + timedelta(days=2)
        sessions = [
            {'title': 'Power BI foundations', 'scheduled_date': starts.date().isoformat(), 'scheduled_time': starts.time().strftime('%H:%M'), 'duration_minutes': 60},
            {'title': 'Power BI dashboards', 'scheduled_date': (starts + timedelta(days=1)).date().isoformat(), 'scheduled_time': starts.time().strftime('%H:%M'), 'duration_minutes': 90},
        ]
        cover = SimpleUploadedFile('programme.png', b'programme-cover', content_type='image/png')
        response = self.client.post('/api/live-classes/educator/programs/', {
            'title': 'Power BI programme', 'description': 'Two guided sessions', 'category': 'Data',
            'level': 'beginner', 'learning_objectives': 'Build a dashboard', 'requirements': 'Power BI Desktop',
            'price': '15000', 'currency': 'NGN', 'capacity': '25', 'recording_enabled': 'true',
            'sessions': json.dumps(sessions), 'cover_image': cover,
        }, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        bundle = LiveClassBundle.objects.get(title='Power BI programme')
        self.assertEqual(bundle.classes.count(), 2)
        self.assertEqual(list(bundle.classes.values_list('title', flat=True)), ['Power BI foundations', 'Power BI dashboards'])
        self.assertTrue(all(item.access_type == 'paid' and item.price == bundle.price for item in bundle.classes.all()))
        self.assertEqual(sum(item.reminders.count() for item in bundle.classes.all()), 6)

    def test_program_creation_is_atomic_when_one_session_is_invalid(self):
        starts = timezone.localtime() + timedelta(days=2)
        response = self.client.post('/api/live-classes/educator/programs/', {
            'title': 'Invalid programme', 'description': 'Should roll back', 'category': 'Data',
            'level': 'beginner', 'learning_objectives': 'Learn', 'price': '5000', 'currency': 'NGN',
            'capacity': '10', 'sessions': json.dumps([
                {'title': 'Valid', 'scheduled_date': starts.date().isoformat(), 'scheduled_time': starts.time().strftime('%H:%M'), 'duration_minutes': 60},
                {'title': '', 'scheduled_date': starts.date().isoformat(), 'scheduled_time': starts.time().strftime('%H:%M'), 'duration_minutes': 60},
            ]), 'cover_image': SimpleUploadedFile('programme.png', b'not-a-real-image', content_type='image/png'),
        }, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(LiveClassBundle.objects.filter(title='Invalid programme').exists())

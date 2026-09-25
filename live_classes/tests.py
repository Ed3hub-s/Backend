from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
import json
import requests
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import APIException
from rest_framework.test import APITestCase

from authentication.models import UserProfile

from .models import LiveClass, LiveClassPayment, LiveClassRegistration
from .services import CloudflareRealtimeKitV1, ProviderConfigurationError, ProviderResourceNotFound


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

    @override_settings(
        CLOUDFLARE_ACCOUNT_ID='account',
        CLOUDFLARE_REALTIMEKIT_APP_ID='app',
        CLOUDFLARE_REALTIMEKIT_API_TOKEN='token',
        CLOUDFLARE_REALTIMEKIT_INSTRUCTOR_PRESET='webinar_presenter',
        CLOUDFLARE_REALTIMEKIT_STUDENT_PRESET='webinar_viewer',
    )
    @patch('live_classes.services.CloudflareRealtimeKitV1._request')
    def test_host_and_student_join_the_same_interactive_room(self, request):
        live_class = self.make_class(minutes_from_now=5)
        LiveClassRegistration.objects.create(
            live_class=live_class, learner=self.learner,
            registration_status='confirmed', access_status='active',
        )
        request.side_effect = [
            {'id': 'shared-room'},
            {'id': 'host', 'token': 'host-token'},
            {'id': 'student', 'token': 'student-token'},
        ]
        self.client.force_authenticate(self.educator)
        host = self.client.post(f'/api/live-classes/{live_class.slug}/join/')
        self.client.force_authenticate(self.learner)
        student = self.client.post(f'/api/live-classes/{live_class.slug}/join/')
        self.assertEqual(host.status_code, 200)
        self.assertEqual(student.status_code, 200)
        self.assertEqual(host.data['meeting_id'], student.data['meeting_id'])
        self.assertEqual(request.call_args_list[1].args[2]['preset_name'], 'group_call_host')
        self.assertEqual(request.call_args_list[2].args[2]['preset_name'], 'group_call_participant')
        # A caller holding the original stale object must reuse the saved room.
        self.assertEqual(CloudflareRealtimeKitV1().ensure_meeting(live_class), 'shared-room')
        self.assertEqual(request.call_count, 3)

    def test_educator_can_start_scheduled_class_now(self):
        live_class = self.make_class(minutes_from_now=3 * 24 * 60)
        self.client.force_authenticate(self.educator)

        response = self.client.patch(
            f'/api/live-classes/educator/{live_class.slug}/',
            {'start_now': True, 'status': 'published'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        live_class.refresh_from_db()
        self.assertLess(abs((live_class.starts_at - timezone.now()).total_seconds()), 60)
        self.assertTrue(live_class.is_joinable())

    def test_educator_can_reschedule_class(self):
        live_class = self.make_class(minutes_from_now=3 * 24 * 60)
        new_start = timezone.localtime() + timedelta(days=1)
        self.client.force_authenticate(self.educator)

        response = self.client.patch(
            f'/api/live-classes/educator/{live_class.slug}/',
            {
                'scheduled_date': new_start.date().isoformat(),
                'scheduled_time': new_start.strftime('%H:%M'),
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        live_class.refresh_from_db()
        self.assertEqual(live_class.scheduled_date, new_start.date())
        self.assertEqual(live_class.scheduled_time.strftime('%H:%M'), new_start.strftime('%H:%M'))

    def test_educator_can_delete_unregistered_class(self):
        live_class = self.make_class()
        self.client.force_authenticate(self.educator)

        response = self.client.delete(f'/api/live-classes/educator/{live_class.slug}/')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(LiveClass.objects.filter(pk=live_class.pk).exists())

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


@override_settings(
    CLOUDFLARE_ACCOUNT_ID='account-id',
    CLOUDFLARE_REALTIMEKIT_APP_ID='app-id',
    CLOUDFLARE_REALTIMEKIT_API_TOKEN='api-token',
)
class CloudflareRealtimeKitTests(SimpleTestCase):
    @patch('live_classes.services.requests.request')
    def test_permission_failure_has_actionable_safe_message(self, mocked_request):
        mocked_request.return_value = Mock(
            ok=False,
            status_code=403,
            json=Mock(return_value={
                'success': False,
                'errors': [{'code': 10000, 'message': 'Authentication error'}],
            }),
        )

        with self.assertRaisesMessage(
            ProviderConfigurationError,
            'not authorized to create classrooms',
        ):
            CloudflareRealtimeKitV1()._request('POST', '/meetings', {})

    @patch('live_classes.services.requests.request')
    def test_unreachable_provider_has_retryable_message(self, mocked_request):
        mocked_request.side_effect = requests.ConnectionError('offline')

        with self.assertRaisesMessage(APIException, 'temporarily unreachable'):
            CloudflareRealtimeKitV1()._request('POST', '/meetings', {})

    @override_settings(CLOUDFLARE_REALTIMEKIT_STUDENT_PRESET='webinar_viewer')
    def test_rejoining_viewer_is_upgraded_before_token_refresh(self):
        provider = CloudflareRealtimeKitV1()
        provider.ensure_meeting = Mock(return_value='room')
        provider._request = Mock(side_effect=[{}, {'token': 'fresh-token'}])
        user = Mock(username='student', pk=2)
        user.get_full_name.return_value = ''
        result = provider.participant_token(Mock(pk=1), user, 'learner', 'saved-student')
        self.assertEqual(result, ('saved-student', 'fresh-token'))
        self.assertEqual(provider._request.call_args_list[0].args, (
            'PATCH', '/meetings/room/participants/saved-student',
            {'name': 'student', 'preset_name': 'group_call_participant'},
        ))
        self.assertEqual(provider._request.call_args_list[1].args[1],
                         '/meetings/room/participants/saved-student/token')

    def test_permission_failure_does_not_create_duplicate_participants(self):
        provider = CloudflareRealtimeKitV1()
        provider.ensure_meeting = Mock(return_value='room')
        provider._request = Mock(side_effect=ProviderConfigurationError())
        user = Mock(username='student', pk=2)
        user.get_full_name.return_value = ''
        with self.assertRaises(ProviderConfigurationError):
            provider.participant_token(Mock(pk=1), user, 'learner', 'saved-student')
        self.assertEqual(provider._request.call_count, 1)

    def test_deleted_participant_is_replaced(self):
        provider = CloudflareRealtimeKitV1()
        provider.ensure_meeting = Mock(return_value='room')
        provider._request = Mock(side_effect=[
            ProviderResourceNotFound(), {'id': 'replacement', 'token': 'new-token'},
        ])
        user = Mock(username='student', pk=2)
        user.get_full_name.return_value = ''
        self.assertEqual(provider.participant_token(Mock(pk=1), user, 'learner', 'deleted'),
                         ('replacement', 'new-token'))
        self.assertEqual(provider._request.call_args.args[1], '/meetings/room/participants')

    @override_settings(CLOUDFLARE_REALTIMEKIT_STUDENT_PRESET='custom_classroom_student')
    def test_custom_presets_are_preserved(self):
        self.assertEqual(CloudflareRealtimeKitV1().participant_preset('learner'),
                         'custom_classroom_student')

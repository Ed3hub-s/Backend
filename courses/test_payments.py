import hashlib
import hmac
import json
import requests
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APITestCase

from .admin import LessonAdmin
from .models import Course, CoursePayment, EducatorTransaction, EducatorWallet, Enrollment, Lesson, Module
from .payments import has_course_access


@override_settings(PAYSTACK_SECRET_KEY='test-secret', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CoursePaymentTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user('teacher', 'teacher@example.com')
        self.learner = User.objects.create_user('learner', 'learner@example.com')
        self.course = Course.objects.create(instructor=self.teacher, title='Data', slug='data', description='Learn', price=100, is_published=True)
        self.module = Module.objects.create(course=self.course, title='Module')
        self.lesson = Lesson.objects.create(module=self.module, title='Private lesson', video_file='courses/videos/lesson.mp4', content='Paid content', transcript='Paid transcript')
        self.payment = CoursePayment.objects.create(course=self.course, learner=self.learner, reference='COURSE-test', amount=100, customer_email=self.learner.email)
        self.client.force_authenticate(self.learner)
        self.endpoint = f'/api/courses/{self.course.pk}/enroll/'

    def verification(self, **changes):
        data = {'status': 'success', 'amount': 10000, 'currency': 'NGN', 'reference': self.payment.reference, 'customer': {'email': self.learner.email}}
        data.update(changes)
        return Mock(raise_for_status=Mock(), json=Mock(return_value={'status': True, 'data': data}))

    def webhook(self, event, data, signature=None):
        payload = json.dumps({'event': event, 'data': data}).encode()
        signature = signature or hmac.new(b'test-secret', payload, hashlib.sha512).hexdigest()
        return self.client.post('/api/live-classes/webhooks/paystack/', payload, content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature)

    @patch('core.payments.requests.request')
    def test_checkout_uses_server_price_and_account_email_without_enrolling(self, request):
        def initialize(*args, **kwargs):
            reference = kwargs['json']['reference']
            return Mock(raise_for_status=Mock(), json=Mock(return_value={'status': True, 'data': {'reference': reference, 'authorization_url': f'https://checkout.paystack.com/{reference}'}}))

        request.side_effect = initialize
        response = self.client.post(self.endpoint, {'amount': 1, 'email': 'attacker@example.com'}, format='json')
        self.assertEqual(response.status_code, 202)
        self.assertFalse(Enrollment.objects.exists())
        self.assertFalse(EducatorTransaction.objects.exists())
        self.assertEqual(request.call_args.kwargs['json']['amount'], 10000)
        self.assertEqual(request.call_args.kwargs['json']['email'], self.learner.email)
        first_checkout = response.data['checkout']
        response = self.client.post(self.endpoint)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(request.call_count, 2)
        self.assertNotEqual(first_checkout['reference'], response.data['checkout']['reference'])
        self.assertNotEqual(first_checkout['authorization_url'], response.data['checkout']['authorization_url'])

    @patch('core.payments.requests.request')
    def test_verification_is_idempotent_and_credits_only_once(self, request):
        request.return_value = self.verification()
        for _ in range(2):
            self.assertEqual(self.client.post(self.endpoint, {'reference': self.payment.reference}).status_code, 200)
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(EducatorTransaction.objects.count(), 1)
        self.assertEqual(EducatorWallet.objects.get().balance, Decimal('60.00'))
        self.assertEqual(request.call_count, 1)
        self.assertTrue(has_course_access(self.course, self.learner))

    @patch('core.payments.requests.request')
    def test_rejects_mismatched_or_failed_payments(self, request):
        for changes in ({'amount': 1}, {'amount': '10000'}, {'currency': 'USD'}, {'reference': 'other'}, {'customer': {'email': 'other@example.com'}}, {'status': 'failed'}):
            with self.subTest(changes=changes):
                request.return_value = self.verification(**changes)
                self.assertEqual(self.client.post(self.endpoint, {'reference': self.payment.reference}).status_code, 400)
                self.assertFalse(Enrollment.objects.exists())

    @patch('core.payments.requests.request')
    def test_reference_cannot_be_reused_by_another_learner_or_course(self, request):
        stranger = User.objects.create_user('stranger', 'stranger@example.com')
        self.client.force_authenticate(stranger)
        self.assertEqual(self.client.post(self.endpoint, {'reference': self.payment.reference}).status_code, 400)
        self.client.force_authenticate(self.learner)
        other = Course.objects.create(instructor=self.teacher, title='Other', slug='other', price=100, is_published=True)
        self.assertEqual(self.client.post(f'/api/courses/{other.pk}/enroll/', {'reference': self.payment.reference}).status_code, 400)
        request.assert_not_called()

    @patch('core.payments.requests.request')
    def test_webhook_and_refund_revoke_access_and_reverse_educator_credit(self, request):
        request.return_value = self.verification()
        self.assertEqual(self.webhook('charge.success', {'reference': self.payment.reference}).status_code, 200)
        self.assertTrue(has_course_access(self.course, self.learner))
        for _ in range(2):
            self.assertEqual(self.webhook('refund.processed', {'transaction_reference': self.payment.reference, 'amount': 10000, 'currency': 'NGN'}).status_code, 200)
        self.assertFalse(has_course_access(self.course, self.learner))
        self.assertEqual(EducatorWallet.objects.get().balance, 0)
        self.assertEqual(self.client.get(f'/api/courses/enrolled/{self.course.pk}/').status_code, 403)
        self.assertEqual(self.client.post(self.endpoint, {'reference': self.payment.reference}).status_code, 400)
        self.assertEqual(self.webhook('charge.success', {'reference': self.payment.reference}).status_code, 200)
        self.assertEqual(request.call_count, 1)

    def test_forged_webhook_is_rejected(self):
        self.assertEqual(self.webhook('charge.success', {'reference': self.payment.reference}, 'forged').status_code, 401)
        self.assertFalse(Enrollment.objects.exists())

    def test_public_detail_and_unverified_enrollment_do_not_expose_paid_content(self):
        Enrollment.objects.create(course=self.course, learner=self.learner)
        response = self.client.get('/api/courses/data/')
        self.assertEqual(response.status_code, 200)
        lesson = response.data['modules'][0]['lessons'][0]
        self.assertIsNone(lesson['video_url'])
        self.assertEqual(lesson['content'], '')
        self.assertEqual(lesson['transcript'], '')
        self.assertEqual(self.client.get(f'/api/courses/enrolled/{self.course.pk}/').status_code, 403)
        self.assertEqual(self.client.post(f'/api/courses/lessons/{self.lesson.pk}/complete/').status_code, 403)

    def test_admin_and_educator_can_review_video(self):
        staff = User.objects.create_user('staff', is_staff=True)
        for viewer in (staff, self.teacher):
            self.client.force_authenticate(viewer)
            response = self.client.get('/api/courses/data/')
            self.assertTrue(response.data['modules'][0]['lessons'][0]['video_url'])
        preview = LessonAdmin(Lesson, AdminSite()).video_preview(self.lesson)
        self.assertIn('<video controls', preview)
        self.assertIn('lesson.mp4', preview)

    @override_settings(PAYSTACK_SECRET_KEY='')
    def test_missing_gateway_fails_closed(self):
        self.assertEqual(self.client.post(self.endpoint).status_code, 503)
        self.assertFalse(Enrollment.objects.exists())

    def test_free_enrollment_needs_no_payment(self):
        self.course.is_free = True
        self.course.save()
        self.assertEqual(self.client.post(self.endpoint).status_code, 201)
        self.assertTrue(has_course_access(self.course, self.learner))

    @patch('core.payments.requests.request')
    def test_provider_timeout_does_not_grant_access(self, request):
        request.side_effect = requests.Timeout()
        self.assertEqual(self.client.post(self.endpoint, {'reference': self.payment.reference}).status_code, 500)
        self.assertFalse(Enrollment.objects.exists())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    @patch('core.payments.requests.request')
    def test_invoice_price_survives_later_course_price_change(self, request):
        self.course.price = 500
        self.course.save()
        request.return_value = self.verification()
        self.assertEqual(self.client.post(self.endpoint, {'reference': self.payment.reference}).status_code, 200)
        self.assertEqual(EducatorWallet.objects.get().balance, Decimal('60.00'))

    def test_real_lesson_endpoint_denies_unpaid_learners_but_allows_previews(self):
        endpoint = f'/api/courses/lessons/{self.lesson.pk}/'
        self.assertEqual(self.client.get(endpoint).status_code, 403)
        self.lesson.is_free_preview = True
        self.lesson.save()
        self.assertEqual(self.client.get(endpoint).status_code, 200)

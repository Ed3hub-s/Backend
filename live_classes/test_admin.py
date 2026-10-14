from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import LiveClass, LiveClassPayment, LiveClassRegistration


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LiveClassAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin-live', 'admin-live@example.com', 'pass')
        self.educator = User.objects.create_user('teacher-live', 'teacher-live@example.com')
        self.learner = User.objects.create_user(
            'live-buyer', 'live-buyer@example.com', first_name='Live', last_name='Buyer',
        )
        starts = timezone.localtime() + timedelta(days=1)
        self.live_class = LiveClass.objects.create(
            educator=self.educator, title='Admin workshop', description='Workshop',
            category='Technology', level='beginner', scheduled_date=starts.date(),
            scheduled_time=starts.time(), duration_minutes=60, capacity=10,
            learning_objectives='Learn', access_type='paid', price=Decimal('2500.00'), status='published',
        )
        self.payment = LiveClassPayment.objects.create(
            user=self.learner, amount=Decimal('2500.00'), currency='NGN',
            transaction_reference='LC-admin', status='successful', educator_share=Decimal('2000.00'),
        )
        LiveClassRegistration.objects.create(
            live_class=self.live_class, learner=self.learner, payment=self.payment,
            registration_status='confirmed', access_status='active', amount_paid=Decimal('2500.00'),
        )
        self.client.force_login(self.admin)

    def test_live_class_admin_shows_count_names_revenue_and_payment(self):
        response = self.client.get(reverse('admin:live_classes_liveclass_changelist'))
        self.assertContains(response, 'Live Buyer')
        self.assertContains(response, 'NGN 2500')

        response = self.client.get(reverse('admin:live_classes_liveclass_change', args=[self.live_class.pk]))
        self.assertContains(response, 'live-buyer@example.com')
        self.assertContains(response, 'LC-admin')

        response = self.client.get(reverse('admin:live_classes_liveclasspayment_changelist'))
        self.assertContains(response, 'Admin workshop')
        self.assertContains(response, '2000.00')

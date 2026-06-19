from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import UserProfile
from courses.models import Course

from .models import AnalyticsEvent
from .services import track_event


class AnalyticsSummaryViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.educator = User.objects.create_user(username='educator', password='pass')
        self.other_educator = User.objects.create_user(username='other', password='pass')
        self.learner = User.objects.create_user(username='learner', password='pass')
        UserProfile.objects.create(user=self.educator, role='educator')
        UserProfile.objects.create(user=self.other_educator, role='educator')
        UserProfile.objects.create(user=self.learner, role='learner')
        self.course = Course.objects.create(
            instructor=self.educator,
            title='Creator Course',
            slug='creator-course',
            description='Course',
            is_published=True,
        )
        self.other_course = Course.objects.create(
            instructor=self.other_educator,
            title='Other Course',
            slug='other-course',
            description='Other course',
            is_published=True,
        )

    def test_summary_is_scoped_to_authenticated_educator_courses(self):
        self.client.force_authenticate(user=self.educator)
        track_event(None, AnalyticsEvent.COURSE_PAGE_VIEW, course=self.course)
        track_event(None, AnalyticsEvent.COURSE_COMPLETED, course=self.course)
        track_event(None, AnalyticsEvent.COURSE_PAGE_VIEW, course=self.other_course)

        response = self.client.get('/api/analytics/summary/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['totals']['events'], 2)
        self.assertEqual(response.data['totals']['course_views'], 1)
        self.assertEqual(response.data['totals']['course_completions'], 1)
        self.assertEqual(response.data['top_courses'][0]['title'], 'Creator Course')

    def test_summary_rejects_non_educators(self):
        self.client.force_authenticate(user=self.learner)

        response = self.client.get('/api/analytics/summary/')

        self.assertEqual(response.status_code, 403)

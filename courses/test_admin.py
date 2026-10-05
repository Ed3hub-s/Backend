from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Course, CoursePayment, Lesson, Module


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AdminVideoReviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'test-password')
        teacher = User.objects.create_user('teacher')
        self.course = Course.objects.create(instructor=teacher, title='Draft course', slug='draft-course')
        self.module = Module.objects.create(course=self.course, title='Module')
        self.lesson = Lesson.objects.create(
            module=self.module, title='Uploaded lesson', video_file='courses/videos/review.mp4',
        )
        self.client.force_login(self.admin)

    def test_lesson_and_module_admin_render_uploaded_video(self):
        for model, obj in [('lesson', self.lesson), ('module', self.module)]:
            response = self.client.get(reverse(f'admin:courses_{model}_change', args=[obj.pk]))
            self.assertContains(response, '<video controls')
            self.assertContains(response, self.lesson.video_file.url)
            self.assertContains(response, 'Open video')

    def test_staff_with_view_permission_can_watch_without_editing(self):
        reviewer = User.objects.create_user('reviewer', is_staff=True)
        reviewer.user_permissions.add(Permission.objects.get(content_type__app_label='courses', codename='view_lesson'))
        self.client.force_login(reviewer)
        url = reverse('admin:courses_lesson_change', args=[self.lesson.pk])
        self.assertContains(self.client.get(url), '<video controls')
        self.assertEqual(self.client.post(url, {'title': 'Changed'}).status_code, 403)

    def test_payment_admin_uses_payment_fields(self):
        payment = CoursePayment.objects.create(
            course=self.course, learner=self.admin, amount=100, reference='ADMIN-test', customer_email=self.admin.email,
        )
        response = self.client.get(reverse('admin:courses_coursepayment_change', args=[payment.pk]))
        self.assertContains(response, 'ADMIN-test')

    def test_missing_video_has_clear_empty_state(self):
        self.lesson.video_file = ''
        self.lesson.save(update_fields=['video_file'])
        response = self.client.get(reverse('admin:courses_lesson_change', args=[self.lesson.pk]))
        self.assertContains(response, 'No video uploaded.')
        self.assertNotContains(response, '<video controls')

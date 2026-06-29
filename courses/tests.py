import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import AffiliateMarketer, AffiliateReferral, MarketerWallet, UserProfile
from authentication.utils import credit_verified_referral_signup
from .models import (
    Assessment,
    Choice,
    Course,
    Enrollment,
    Lesson,
    LessonProgress,
    Module,
    Question,
    Quiz,
    TokenTransaction,
    TokenWallet,
)


class CourseUpdateSyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.instructor = User.objects.create_user(username='educator', password='pass')
        self.learner = User.objects.create_user(username='learner', password='pass')
        self.course = Course.objects.create(
            instructor=self.instructor,
            title='Original Course',
            slug='original-course',
            description='Original description',
            is_published=True,
            is_free=True,
        )
        self.module = Module.objects.create(course=self.course, title='Old Module', order=1)
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Old Lesson',
            lesson_type='video',
            order=1,
            duration_minutes=5,
            content='Old content',
        )
        self.removed_lesson = Lesson.objects.create(
            module=self.module,
            title='Removed Lesson',
            lesson_type='reading',
            order=2,
            duration_minutes=4,
        )
        self.removed_module = Module.objects.create(course=self.course, title='Removed Module', order=2)
        Lesson.objects.create(module=self.removed_module, title='Removed Module Lesson', order=1)
        self.quiz = Quiz.objects.create(module=self.module, title='Old Quiz')
        self.question = Question.objects.create(quiz=self.quiz, text='Old question?', order=1)
        Choice.objects.create(question=self.question, text='Old answer', is_correct=True)
        self.assessment = Assessment.objects.create(
            course=self.course,
            module=self.module,
            title='Old assessment',
            description='Old expected answer',
        )
        self.enrollment = Enrollment.objects.create(learner=self.learner, course=self.course)
        LessonProgress.objects.create(enrollment=self.enrollment, lesson=self.lesson, completed=True)

    def patch_course_modules(self, modules):
        self.client.force_authenticate(self.instructor)
        return self.client.patch(
            f'/api/courses/{self.course.id}/update/',
            {
                'title': 'Updated Course',
                'modules': json.dumps(modules),
            },
            format='multipart',
        )

    def test_update_syncs_submitted_structure_to_enrolled_course_detail(self):
        response = self.patch_course_modules([
            {
                'id': str(self.module.id),
                'title': 'Updated Module',
                'lessons': [
                    {
                        'id': str(self.lesson.id),
                        'title': 'Updated Lesson',
                        'type': 'text',
                        'duration': '12 min',
                        'content': 'Updated content',
                    },
                    {
                        'id': '999999999999',
                        'title': 'New Lesson',
                        'type': 'video',
                        'duration': '7 min',
                    },
                ],
                'quizzes': [
                    {
                        'question': 'Updated quiz?',
                        'type': 'mcq',
                        'options': ['Wrong', 'Right'],
                        'correctAnswer': 'Right',
                    }
                ],
                'assessments': [
                    {
                        'id': str(self.assessment.id),
                        'question': 'Updated assessment',
                        'type': 'short_answer',
                        'expectedAnswer': 'Updated expected answer',
                    }
                ],
            }
        ])

        self.assertEqual(response.status_code, 200)
        self.course.refresh_from_db()
        self.enrollment.refresh_from_db()
        self.assertEqual(self.course.title, 'Updated Course')
        self.assertEqual(self.course.modules.count(), 1)
        self.assertFalse(Module.objects.filter(id=self.removed_module.id).exists())
        self.assertFalse(Lesson.objects.filter(id=self.removed_lesson.id).exists())
        self.assertEqual(self.enrollment.progress_percent, 50)
        self.assertFalse(self.enrollment.completed)

        module = self.course.modules.get()
        self.assertEqual(module.title, 'Updated Module')
        self.assertEqual(list(module.lessons.values_list('title', flat=True)), ['Updated Lesson', 'New Lesson'])
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.lesson_type, 'reading')
        self.assertEqual(self.lesson.duration_minutes, 12)
        self.assertEqual(self.lesson.content, 'Updated content')

        quiz = module.quiz
        self.assertEqual(quiz.questions.count(), 1)
        question = quiz.questions.get()
        self.assertEqual(question.text, 'Updated quiz?')
        self.assertEqual(question.choices.get(is_correct=True).text, 'Right')

        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.title, 'Updated assessment')
        self.assertEqual(self.assessment.description, 'Updated expected answer')

        self.client.force_authenticate(self.learner)
        detail = self.client.get(f'/api/courses/enrolled/{self.course.id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['title'], 'Updated Course')
        self.assertEqual(detail.data['modules'][0]['title'], 'Updated Module')
        self.assertEqual(detail.data['modules'][0]['lessons'][0]['title'], 'Updated Lesson')

    def test_update_with_empty_modules_removes_stale_student_content(self):
        response = self.patch_course_modules([])

        self.assertEqual(response.status_code, 200)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.course.modules.count(), 0)
        self.assertEqual(self.enrollment.progress_percent, 0)
        self.assertFalse(self.enrollment.completed)

        self.client.force_authenticate(self.learner)
        detail = self.client.get(f'/api/courses/enrolled/{self.course.id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['modules'], [])

    def test_create_parses_frontend_multipart_modules_as_full_structure(self):
        self.client.force_authenticate(self.instructor)
        response = self.client.post(
            '/api/courses/create/',
            {
                'title': 'New Course',
                'slug': 'new-course',
                'description': 'New description',
                'skill_level': 'beginner',
                'price': '0',
                'is_free': 'true',
                'is_published': 'true',
                'estimated_hours': '2',
                'duration_weeks': '1',
                'hours_per_week': '1',
                'is_self_paced': 'true',
                'modules': json.dumps([
                    {
                        'id': 'tmp-1',
                        'title': 'First Module',
                        'lessons': [{'id': 'lesson-tmp-1', 'title': 'First Lesson', 'type': 'text'}],
                        'quizzes': [{'question': 'First quiz?', 'type': 'true_false', 'correctAnswer': 'True'}],
                        'assessments': [{'question': 'First assessment', 'expectedAnswer': 'Expected'}],
                    },
                    {
                        'id': 'tmp-2',
                        'title': 'Second Module',
                        'lessons': [{'id': 'lesson-tmp-2', 'title': 'Second Lesson', 'type': 'video'}],
                        'quizzes': [],
                        'assessments': [],
                    },
                ]),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        course = Course.objects.get(slug='new-course')
        self.assertEqual(list(course.modules.values_list('title', flat=True)), ['First Module', 'Second Module'])
        first_module = course.modules.get(order=1)
        self.assertEqual(first_module.lessons.get().title, 'First Lesson')
        self.assertEqual(first_module.quiz.questions.get().text, 'First quiz?')
        self.assertEqual(first_module.assessments.get().title, 'First assessment')


class CourseCompletionRewardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.instructor = User.objects.create_user(username='educator', password='pass')
        self.learner = User.objects.create_user(username='learner', password='pass')
        self.course = Course.objects.create(
            instructor=self.instructor,
            title='Reward Course',
            slug='reward-course',
            description='Reward description',
            is_published=True,
            is_free=True,
            completion_tokens=50,
        )
        self.module = Module.objects.create(course=self.course, title='Reward Module', order=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Reward Lesson', order=1)
        self.enrollment = Enrollment.objects.create(learner=self.learner, course=self.course)

    def test_course_completion_awards_learner_and_creator_tokens(self):
        self.client.force_authenticate(self.learner)

        response = self.client.post(f'/api/courses/lessons/{self.lesson.id}/complete/')

        self.assertEqual(response.status_code, 200)
        self.enrollment.refresh_from_db()
        self.assertTrue(self.enrollment.completed)

        learner_wallet = TokenWallet.objects.get(learner=self.learner)
        creator_wallet = TokenWallet.objects.get(learner=self.instructor)
        learner_tx = TokenTransaction.objects.get(wallet=learner_wallet, reason='course_complete')
        creator_tx = TokenTransaction.objects.get(wallet=creator_wallet, reason='course_complete')

        self.assertEqual(learner_tx.amount, 50)
        self.assertEqual(creator_tx.amount, 50)
        self.assertEqual(learner_tx.description, 'Completed course: Reward Course')
        self.assertEqual(creator_tx.description, 'learner completed your course: Reward Course')

    def test_repeating_completed_lesson_does_not_duplicate_course_rewards(self):
        self.client.force_authenticate(self.learner)

        self.client.post(f'/api/courses/lessons/{self.lesson.id}/complete/')
        self.client.post(f'/api/courses/lessons/{self.lesson.id}/complete/')

        self.assertEqual(TokenTransaction.objects.filter(reason='course_complete').count(), 2)

    def test_instructor_completing_own_course_gets_single_completion_reward(self):
        own_course = Course.objects.create(
            instructor=self.instructor,
            title='Own Course',
            slug='own-course',
            description='Own description',
            is_published=True,
            is_free=True,
            completion_tokens=25,
        )
        own_module = Module.objects.create(course=own_course, title='Own Module', order=1)
        own_lesson = Lesson.objects.create(module=own_module, title='Own Lesson', order=1)
        Enrollment.objects.create(learner=self.instructor, course=own_course)

        self.client.force_authenticate(self.instructor)
        response = self.client.post(f'/api/courses/lessons/{own_lesson.id}/complete/')

        self.assertEqual(response.status_code, 200)
        wallet = TokenWallet.objects.get(learner=self.instructor)
        self.assertEqual(
            TokenTransaction.objects.filter(wallet=wallet, reason='course_complete', amount=25).count(),
            1,
        )


class AffiliateCommissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.instructor = User.objects.create_user(username='teacher', password='pass')
        self.marketer = User.objects.create_user(username='marketer', password='pass', is_active=True)
        UserProfile.objects.create(user=self.marketer, role='marketer')
        self.learner = User.objects.create_user(username='buyer', email='buyer@example.com', password='pass', is_active=True)
        self.course = Course.objects.create(
            instructor=self.instructor,
            title='Paid Course',
            slug='paid-course',
            description='Paid description',
            price=Decimal('100.00'),
            is_free=False,
            is_published=True,
        )

    def test_first_paid_enrollment_credits_marketer_once(self):
        affiliate = AffiliateMarketer.objects.get(user=self.marketer)
        referral = AffiliateReferral.objects.create(
            marketer=self.marketer,
            referred_user=self.learner,
            referral_code=affiliate.referral_code,
        )
        credit_verified_referral_signup(self.learner)

        self.client.force_authenticate(self.learner)
        response = self.client.post(f'/api/courses/{self.course.id}/enroll/')
        self.assertEqual(response.status_code, 201)

        referral.refresh_from_db()
        wallet = MarketerWallet.objects.get(marketer=self.marketer)
        self.assertTrue(referral.signup_bonus_paid)
        self.assertTrue(referral.first_purchase_reward_paid)
        self.assertEqual(wallet.balance, Decimal('25.00'))
        self.assertEqual(wallet.transactions.count(), 2)

        duplicate_response = self.client.post(f'/api/courses/{self.course.id}/enroll/')
        self.assertEqual(duplicate_response.status_code, 200)
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('25.00'))
        self.assertEqual(wallet.transactions.count(), 2)

import json

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

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

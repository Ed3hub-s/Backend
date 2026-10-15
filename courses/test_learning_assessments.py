from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Assessment,
    AssessmentSubmission,
    Choice,
    Course,
    Enrollment,
    Module,
    Question,
    Quiz,
    QuizAttempt,
    TokenTransaction,
)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LearnerQuizAssessmentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.educator = User.objects.create_user('quiz-teacher', 'teacher@example.com')
        self.learner = User.objects.create_user('quiz-learner', 'learner@example.com')
        self.outsider = User.objects.create_user('quiz-outsider', 'outsider@example.com')
        self.course = Course.objects.create(
            instructor=self.educator,
            title='Secure testing',
            slug='secure-testing',
            description='Course',
            is_free=True,
            is_published=True,
        )
        Enrollment.objects.create(course=self.course, learner=self.learner)
        self.module = Module.objects.create(course=self.course, title='Module one')
        self.quiz = Quiz.objects.create(module=self.module, title='Module quiz', pass_score=50, reward_tokens=7)
        self.question_one = Question.objects.create(quiz=self.quiz, text='First?', order=1)
        self.correct_one = Choice.objects.create(question=self.question_one, text='Correct', is_correct=True)
        self.wrong_one = Choice.objects.create(question=self.question_one, text='Wrong', is_correct=False)
        self.question_two = Question.objects.create(quiz=self.quiz, text='Second?', order=2)
        self.correct_two = Choice.objects.create(question=self.question_two, text='Correct two', is_correct=True)
        self.wrong_two = Choice.objects.create(question=self.question_two, text='Wrong two', is_correct=False)
        self.assessment = Assessment.objects.create(
            course=self.course,
            module=self.module,
            title='Written task',
            description='Explain the topic.',
            pass_score=70,
            reward_tokens=11,
        )

    def test_learner_payload_never_exposes_correct_answers(self):
        self.client.force_authenticate(self.learner)
        response = self.client.get(f'/api/courses/enrolled/{self.course.pk}/')
        self.assertEqual(response.status_code, 200)
        choices = response.data['modules'][0]['quiz']['questions'][0]['choices']
        self.assertNotIn('is_correct', choices[0])

        response = self.client.get(f'/api/courses/quizzes/{self.quiz.pk}/attempt/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('is_correct', response.data['quiz']['questions'][0]['choices'][0])

    def test_quiz_is_scored_server_side_and_rewarded_only_once(self):
        self.client.force_authenticate(self.learner)
        endpoint = f'/api/courses/quizzes/{self.quiz.pk}/attempt/'
        answers = [
            {'question_id': self.question_one.pk, 'choice_id': self.correct_one.pk},
            {'question_id': self.question_two.pk, 'choice_id': self.wrong_two.pk},
        ]
        first = self.client.post(endpoint, {'answers': answers}, format='json')
        second = self.client.post(endpoint, {'answers': answers}, format='json')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data['score'], '50.00')
        self.assertTrue(first.data['passed'])
        self.assertTrue(first.data['reward_granted'])
        self.assertFalse(second.data['reward_granted'])
        self.assertEqual(QuizAttempt.objects.count(), 2)
        self.assertEqual(TokenTransaction.objects.filter(reason='quiz_pass', amount=7).count(), 1)

    def test_quiz_rejects_missing_or_cross_question_choices(self):
        self.client.force_authenticate(self.learner)
        endpoint = f'/api/courses/quizzes/{self.quiz.pk}/attempt/'
        missing = self.client.post(endpoint, {'answers': [
            {'question_id': self.question_one.pk, 'choice_id': self.correct_one.pk},
        ]}, format='json')
        crossed = self.client.post(endpoint, {'answers': [
            {'question_id': self.question_one.pk, 'choice_id': self.correct_two.pk},
            {'question_id': self.question_two.pk, 'choice_id': self.correct_two.pk},
        ]}, format='json')
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(crossed.status_code, 400)
        self.assertFalse(QuizAttempt.objects.exists())

    def test_unenrolled_user_cannot_take_quiz_or_submit_assessment(self):
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(f'/api/courses/quizzes/{self.quiz.pk}/attempt/').status_code, 403)
        self.assertEqual(self.client.post(
            f'/api/courses/assessments/{self.assessment.pk}/submit/',
            {'response_text': 'Unauthorized'},
            format='json',
        ).status_code, 403)

    def test_assessment_submission_grading_and_reward(self):
        self.client.force_authenticate(self.learner)
        submit = self.client.post(
            f'/api/courses/assessments/{self.assessment.pk}/submit/',
            {'response_text': 'My complete written response.'},
            format='json',
        )
        self.assertEqual(submit.status_code, 201)
        submission = AssessmentSubmission.objects.get()

        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.patch(
            f'/api/courses/assessment-submissions/{submission.pk}/grade/',
            {'score': 90},
            format='json',
        ).status_code, 403)

        self.client.force_authenticate(self.educator)
        graded = self.client.patch(
            f'/api/courses/assessment-submissions/{submission.pk}/grade/',
            {'score': 85, 'feedback': 'Strong work.'},
            format='json',
        )
        self.assertEqual(graded.status_code, 200)
        self.assertEqual(graded.data['status'], 'graded')
        self.assertEqual(graded.data['score'], '85.00')
        self.assertTrue(graded.data['reward_granted'])
        self.assertEqual(TokenTransaction.objects.filter(reason='assessment_pass', amount=11).count(), 1)

        # Regrading cannot award the same assessment twice.
        self.client.patch(
            f'/api/courses/assessment-submissions/{submission.pk}/grade/',
            {'score': 95, 'feedback': 'Updated.'},
            format='json',
        )
        self.assertEqual(TokenTransaction.objects.filter(reason='assessment_pass', amount=11).count(), 1)

        self.client.force_authenticate(self.learner)
        self.assertEqual(self.client.post(
            f'/api/courses/assessments/{self.assessment.pk}/submit/',
            {'response_text': 'Try to replace graded work.'},
            format='json',
        ).status_code, 400)

    def test_past_due_assessment_rejects_submission(self):
        self.assessment.due_date = timezone.localdate() - timedelta(days=1)
        self.assessment.save(update_fields=('due_date',))
        self.client.force_authenticate(self.learner)
        response = self.client.post(
            f'/api/courses/assessments/{self.assessment.pk}/submit/',
            {'response_text': 'Late work'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_educator_can_view_quiz_results_and_assessment_submissions(self):
        self.client.force_authenticate(self.learner)
        self.client.post(
            f'/api/courses/quizzes/{self.quiz.pk}/attempt/',
            {'answers': [
                {'question_id': self.question_one.pk, 'choice_id': self.correct_one.pk},
                {'question_id': self.question_two.pk, 'choice_id': self.correct_two.pk},
            ]},
            format='json',
        )
        self.client.post(
            f'/api/courses/assessments/{self.assessment.pk}/submit/',
            {'response_text': 'Ready for educator review.'},
            format='json',
        )

        self.client.force_authenticate(self.educator)
        attempts = self.client.get(f'/api/courses/quizzes/{self.quiz.pk}/results/')
        submissions = self.client.get(f'/api/courses/assessments/{self.assessment.pk}/submissions/')

        self.assertEqual(attempts.status_code, 200)
        self.assertEqual(attempts.data[0]['learner_email'], self.learner.email)
        self.assertEqual(submissions.status_code, 200)
        self.assertEqual(submissions.data[0]['response_text'], 'Ready for educator review.')

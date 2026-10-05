from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Q, F
from rest_framework import status, generics, filters, parsers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import json
import re

from authentication.utils import credit_first_purchase_commission
from .payments import purchase_course, require_course_access
from analytics.models import AnalyticsEvent
from analytics.services import track_event
from .models import (
    Category, Course, Module, Lesson, Enrollment, LessonProgress,
    ModuleProgress, Review, TokenWallet, TokenTransaction, Assessment,
    Certificate, Quiz, Question, Choice, Session, SessionRegistration,
    EducatorWallet, EducatorTransaction, WithdrawalRequest, EDUCATOR_SHARE,
)
from .serializers import (
    CategorySerializer, CourseListSerializer, CourseDetailSerializer, CourseWriteSerializer,
    LessonSerializer, ModuleSerializer, EnrollmentSerializer, LessonProgressSerializer,
    ModuleProgressSerializer, ReviewSerializer, TokenWalletSerializer,
    TokenTransactionSerializer, CertificateSerializer, QuizSerializer, AssessmentSerializer,
    SessionSerializer, SessionRegistrationSerializer,
)


def award_tokens(user, amount, reason, description):
    wallet, _ = TokenWallet.objects.get_or_create(learner=user)
    TokenTransaction.objects.create(
        wallet=wallet,
        amount=amount,
        reason=reason,
        description=description,
        is_claimed=False,
    )
    return wallet


def award_course_completion_tokens(enrollment):
    course = enrollment.course
    award_tokens(
        enrollment.learner,
        course.completion_tokens,
        'course_complete',
        f'Completed course: {course.title}',
    )

    if course.instructor_id != enrollment.learner_id:
        award_tokens(
            course.instructor,
            course.completion_tokens,
            'course_complete',
            f'{enrollment.learner.username} completed your course: {course.title}',
        )


def create_course_content(course, modules_data):
    """Create modules with lessons, quizzes, and assessments."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"create_course_content called with {type(modules_data)}")
    logger.info(f"modules_data value: {repr(modules_data)[:500]}")
    
    # Handle if modules_data is still a string (triple-encoded)
    if isinstance(modules_data, str):
        logger.warning("modules_data is still a string, attempting to parse")
        try:
            modules_data = json.loads(modules_data)
            logger.info(f"After parsing string: {type(modules_data)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse modules_data string: {e}")
            return
    
    if not isinstance(modules_data, list):
        logger.error(f"modules_data is not a list: {type(modules_data)}")
        return
    
    logger.info(f"Processing {len(modules_data)} modules")
    
    for idx, module_data in enumerate(modules_data):
        logger.info(f"Module {idx}: type={type(module_data)}")
        
        # Handle if module_data is a string
        if isinstance(module_data, str):
            logger.warning(f"Module {idx} is a string, attempting to parse")
            logger.info(f"Module string value: {repr(module_data)[:300]}")
            try:
                parsed = json.loads(module_data)
                logger.info(f"After parsing module string: {type(parsed)}")
                logger.info(f"Parsed value: {repr(parsed)[:300]}")
                
                # If parsing resulted in a list, take the first element
                if isinstance(parsed, list) and len(parsed) > 0:
                    logger.info(f"Parsed module is a list with {len(parsed)} items, taking first item")
                    module_data = parsed[0]
                    logger.info(f"First item type: {type(module_data)}")
                else:
                    module_data = parsed
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse module {idx}: {e}")
                logger.error(f"Module string was: {repr(module_data)[:300]}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error parsing module {idx}: {e}")
                logger.error(f"Module string was: {repr(module_data)[:300]}")
                continue
        
        if not isinstance(module_data, dict):
            logger.error(f"Module {idx} is not a dict after parsing: {type(module_data)}")
            logger.error(f"Module data: {repr(module_data)[:200]}")
            continue
            
        module = Module.objects.create(
            course=course,
            title=module_data.get('title', f'Module {idx + 1}'),
            order=idx + 1,
            reward_tokens=10
        )
        logger.info(f"Created module: {module.id} - {module.title}")
        
        # Create lessons
        lessons_data = module_data.get('lessons', [])
        logger.info(f"Module {idx} has {len(lessons_data)} lessons")
        
        for lesson_idx, lesson_data in enumerate(lessons_data):
            if not isinstance(lesson_data, dict):
                logger.error(f"Lesson {lesson_idx} is not a dict")
                continue
                
            lesson_type_map = {
                'video': 'video',
                'text': 'reading',
                'document': 'reading'
            }
            lesson_type = lesson_type_map.get(lesson_data.get('type', 'video'), 'video')
            
            # Parse duration string (e.g., "15 min" -> 15)
            duration_str = lesson_data.get('duration', '0')
            duration_minutes = 0
            if duration_str:
                match = re.search(r'(\d+)', str(duration_str))
                if match:
                    duration_minutes = int(match.group(1))
            
            lesson = Lesson.objects.create(
                module=module,
                title=lesson_data.get('title', f'Lesson {lesson_idx + 1}'),
                lesson_type=lesson_type,
                order=lesson_idx + 1,
                duration_minutes=duration_minutes,
                content=lesson_data.get('content', ''),
            )
            logger.info(f"Created lesson: {lesson.id} - {lesson.title}")
        
        # Create quizzes
        quizzes = module_data.get('quizzes', [])
        logger.info(f"Module {idx} has {len(quizzes)} quizzes")
        logger.info(f"Quizzes data: {repr(quizzes)[:300]}")
        
        if quizzes and len(quizzes) > 0:
            quiz = Quiz.objects.create(
                module=module,
                title=f'{module.title} Quiz',
                pass_score=70,
                reward_tokens=5
            )
            logger.info(f"Created quiz: {quiz.id}")
            
            for quiz_idx, quiz_data in enumerate(quizzes):
                logger.info(f"Processing quiz {quiz_idx}: type={type(quiz_data)}")
                
                if not isinstance(quiz_data, dict):
                    logger.error(f"Quiz {quiz_idx} is not a dict: {type(quiz_data)}")
                    continue
                
                question_text = quiz_data.get('question', '')
                if not question_text:
                    logger.warning(f"Quiz {quiz_idx} has no question text, skipping")
                    continue
                    
                question = Question.objects.create(
                    quiz=quiz,
                    text=question_text,
                    order=quiz_idx + 1
                )
                logger.info(f"Created question: {question.id} - {question_text[:50]}")
                
                # Create choices based on quiz type
                quiz_type = quiz_data.get('type', 'mcq')
                logger.info(f"Quiz type: {quiz_type}")
                
                if quiz_type == 'mcq':
                    options = quiz_data.get('options', [])
                    correct_answer = quiz_data.get('correctAnswer', '')
                    logger.info(f"MCQ options: {len(options)}, correct: {correct_answer}")
                    
                    for opt_idx, option in enumerate(options):
                        if option and option.strip():  # Only create non-empty options
                            is_correct = (option == correct_answer or option in correct_answer)
                            choice = Choice.objects.create(
                                question=question,
                                text=option,
                                is_correct=is_correct
                            )
                            logger.info(f"Created choice: {choice.id} - {option[:30]} (correct={is_correct})")
                        
                elif quiz_type == 'true_false':
                    correct_answer = quiz_data.get('correctAnswer', 'True')
                    logger.info(f"True/False correct answer: {correct_answer}")
                    Choice.objects.create(question=question, text='True', is_correct=(correct_answer == 'True'))
                    Choice.objects.create(question=question, text='False', is_correct=(correct_answer == 'False'))
                    logger.info(f"Created True/False choices")
                    
                elif quiz_type == 'fill_blank':
                    correct_answer = quiz_data.get('correctAnswer', '')
                    logger.info(f"Fill blank correct answer: {correct_answer}")
                    if correct_answer:
                        Choice.objects.create(question=question, text=correct_answer, is_correct=True)
                        logger.info(f"Created fill blank choice")
        else:
            logger.info(f"No quizzes to create for module {idx}")
        
        # Create assessments
        assessments_data = module_data.get('assessments', [])
        logger.info(f"Module {idx} has {len(assessments_data)} assessments")
        
        for assessment_data in assessments_data:
            if not isinstance(assessment_data, dict):
                logger.error(f"Assessment is not a dict")
                continue
                
            assessment = Assessment.objects.create(
                course=course,
                module=module,
                title=assessment_data.get('question', 'Assessment')[:255],
                description=assessment_data.get('expectedAnswer', ''),
                assessment_type='graded',
                duration_minutes=20,
                reward_tokens=15
            )
            logger.info(f"Created assessment: {assessment.id}")


def parse_modules_payload(raw_modules):
    """Normalize JSON/FormData module payloads into a list of module dicts."""
    if raw_modules is None:
        return None

    if isinstance(raw_modules, str):
        if not raw_modules.strip():
            return []
        try:
            parsed = json.loads(raw_modules)
        except json.JSONDecodeError as exc:
            raise ValueError(f'Invalid JSON in modules: {exc}') from exc
        return parse_modules_payload(parsed)

    if isinstance(raw_modules, (list, tuple)):
        if not raw_modules:
            return []

        normalized = []
        for item in raw_modules:
            parsed = parse_modules_payload(item) if isinstance(item, str) else item
            if parsed is None:
                continue
            if isinstance(parsed, list):
                normalized.extend(parsed)
            elif isinstance(parsed, dict):
                normalized.append(parsed)
            else:
                raise ValueError('Modules must be a JSON array of objects.')
        return normalized

    if isinstance(raw_modules, dict):
        return [raw_modules]

    raise ValueError('Modules must be a JSON string or list.')


def parse_int_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_int_value(value, default=0):
    parsed = parse_int_id(value)
    return parsed if parsed is not None else default


def parse_duration_minutes(value):
    if value in (None, ''):
        return 0
    match = re.search(r'(\d+)', str(value))
    return int(match.group(1)) if match else 0


def frontend_lesson_type(value):
    return {
        'video': 'video',
        'text': 'reading',
        'document': 'reading',
        'reading': 'reading',
        'quiz': 'quiz',
        'assignment': 'assignment',
    }.get(value or 'video', 'video')


def sync_module_quiz(module, quizzes_data):
    if quizzes_data is None:
        return
    if not isinstance(quizzes_data, list):
        raise ValueError('Module quizzes must be a list.')

    existing_quiz = getattr(module, 'quiz', None)
    if not quizzes_data:
        if existing_quiz:
            existing_quiz.delete()
        return

    quiz, _ = Quiz.objects.get_or_create(
        module=module,
        defaults={
            'title': f'{module.title} Quiz',
            'pass_score': 70,
            'reward_tokens': 5,
        },
    )
    quiz.title = f'{module.title} Quiz'
    quiz.save()
    quiz.questions.all().delete()

    for quiz_idx, quiz_data in enumerate(quizzes_data):
        if not isinstance(quiz_data, dict):
            continue

        question_text = quiz_data.get('question') or quiz_data.get('text') or ''
        if not question_text:
            continue

        question = Question.objects.create(
            quiz=quiz,
            text=question_text,
            order=quiz_idx + 1,
        )

        quiz_type = quiz_data.get('type', 'mcq')
        correct_answer = quiz_data.get('correctAnswer', quiz_data.get('correct_answer', ''))

        if quiz_type == 'true_false':
            correct = str(correct_answer or 'True').strip().lower()
            Choice.objects.create(question=question, text='True', is_correct=correct == 'true')
            Choice.objects.create(question=question, text='False', is_correct=correct == 'false')
            continue

        if quiz_type == 'fill_blank':
            if correct_answer:
                Choice.objects.create(question=question, text=str(correct_answer), is_correct=True)
            continue

        correct_values = correct_answer if isinstance(correct_answer, list) else [correct_answer]
        correct_values = {str(value).strip() for value in correct_values}
        for option in quiz_data.get('options', []):
            if option and str(option).strip():
                Choice.objects.create(
                    question=question,
                    text=str(option),
                    is_correct=str(option).strip() in correct_values,
                )


def sync_module_assessments(course, module, assessments_data):
    if assessments_data is None:
        return
    if not isinstance(assessments_data, list):
        raise ValueError('Module assessments must be a list.')

    existing = list(module.assessments.all().order_by('id'))
    existing_by_id = {assessment.id: assessment for assessment in existing}
    used_ids = set()

    for idx, assessment_data in enumerate(assessments_data):
        if not isinstance(assessment_data, dict):
            continue

        assessment_id = parse_int_id(assessment_data.get('id'))
        assessment = existing_by_id.get(assessment_id)
        if assessment is None and assessment_id is None and idx < len(existing):
            candidate = existing[idx]
            if candidate.id not in used_ids:
                assessment = candidate
        if assessment is None:
            assessment = Assessment(course=course, module=module)

        assessment.title = (
            assessment_data.get('question')
            or assessment_data.get('title')
            or assessment.title
            or 'Assessment'
        )[:255]
        assessment.description = (
            assessment_data.get('expectedAnswer')
            or assessment_data.get('description')
            or ''
        )
        assessment.assessment_type = (
            assessment_data.get('assessment_type')
            if assessment_data.get('assessment_type') in {'graded', 'practice'}
            else assessment.assessment_type or 'graded'
        )
        assessment.duration_minutes = parse_duration_minutes(
            assessment_data.get('duration_minutes', assessment.duration_minutes or 20)
        ) or 20
        assessment.reward_tokens = parse_int_value(
            assessment_data.get('reward_tokens'),
            assessment.reward_tokens or 15,
        )
        assessment.course = course
        assessment.module = module
        assessment.save()
        used_ids.add(assessment.id)

    for assessment in existing:
        if assessment.id not in used_ids:
            assessment.delete()


def sync_module_lessons(module, lessons_data):
    if lessons_data is None:
        return
    if not isinstance(lessons_data, list):
        raise ValueError('Module lessons must be a list.')

    existing = list(module.lessons.all().order_by('order'))
    existing_by_id = {lesson.id: lesson for lesson in existing}
    used_ids = set()

    for lesson_idx, lesson_data in enumerate(lessons_data):
        if not isinstance(lesson_data, dict):
            continue

        lesson_id = parse_int_id(lesson_data.get('id'))
        lesson = existing_by_id.get(lesson_id)
        if lesson is None and lesson_id is None and lesson_idx < len(existing):
            candidate = existing[lesson_idx]
            if candidate.id not in used_ids:
                lesson = candidate
        if lesson is None:
            lesson = Lesson(module=module)

        lesson.title = lesson_data.get('title') or lesson.title or f'Lesson {lesson_idx + 1}'
        lesson.lesson_type = frontend_lesson_type(lesson_data.get('type', lesson_data.get('lesson_type')))
        lesson.order = lesson_idx + 1
        lesson.duration_minutes = parse_duration_minutes(
            lesson_data.get('duration', lesson_data.get('duration_minutes', lesson.duration_minutes))
        )
        if 'content' in lesson_data:
            lesson.content = lesson_data.get('content') or ''
        if 'is_free_preview' in lesson_data:
            lesson.is_free_preview = str(lesson_data.get('is_free_preview')).lower() == 'true'
        lesson.module = module
        lesson.save()
        used_ids.add(lesson.id)

    for lesson in existing:
        if lesson.id not in used_ids:
            if lesson.video_file:
                lesson.video_file.delete(save=False)
            lesson.delete()


def sync_course_content(course, modules_data):
    if modules_data is None:
        return
    if not isinstance(modules_data, list):
        raise ValueError('Modules must be a list.')

    existing = list(course.modules.all().order_by('order'))
    existing_by_id = {module.id: module for module in existing}
    used_ids = set()

    for idx, module_data in enumerate(modules_data):
        if not isinstance(module_data, dict):
            continue

        module_id = parse_int_id(module_data.get('id'))
        module = existing_by_id.get(module_id)
        if module is None and module_id is None and idx < len(existing):
            candidate = existing[idx]
            if candidate.id not in used_ids:
                module = candidate
        if module is None:
            module = Module(course=course)

        module.title = module_data.get('title') or module.title or f'Module {idx + 1}'
        module.order = idx + 1
        module.reward_tokens = parse_int_value(
            module_data.get('reward_tokens'),
            module.reward_tokens or 10,
        )
        module.course = course
        module.save()
        used_ids.add(module.id)

        sync_module_lessons(module, module_data.get('lessons'))
        sync_module_quiz(module, module_data.get('quizzes'))
        sync_module_assessments(course, module, module_data.get('assessments'))

    for module in existing:
        if module.id not in used_ids:
            for lesson in module.lessons.all():
                if lesson.video_file:
                    lesson.video_file.delete(save=False)
            module.delete()


def recalculate_course_enrollments(course):
    total_lessons = Lesson.objects.filter(module__course=course).count()
    for enrollment in course.enrollments.all():
        if total_lessons == 0:
            enrollment.progress_percent = 0
            enrollment.completed = False
            enrollment.completed_at = None
        else:
            completed = LessonProgress.objects.filter(
                enrollment=enrollment,
                completed=True,
                lesson__module__course=course,
            ).count()
            enrollment.progress_percent = round((completed / total_lessons) * 100)
            if enrollment.progress_percent >= 100:
                enrollment.completed = True
                enrollment.completed_at = enrollment.completed_at or timezone.now()
            else:
                enrollment.completed = False
                enrollment.completed_at = None
        enrollment.save(update_fields=('progress_percent', 'completed', 'completed_at'))


# ── Categories ────────────────────────────────────────────────────────────────

class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (AllowAny,)


# ── Courses ───────────────────────────────────────────────────────────────────

class EducatorCourseListView(generics.ListAPIView):
    """Returns all courses (published + draft) created by the authenticated educator."""
    serializer_class = CourseListSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Course.objects.filter(instructor=self.request.user).select_related('instructor', 'category')

    def get_serializer_context(self):
        return {'request': self.request}


class CourseCreateView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def post(self, request):
        import logging
        logger = logging.getLogger(__name__)
        
        data = request.data.copy()
        logger.info(f"Received data keys: {data.keys()}")
        
        data['completion_tokens'] = 10
        
        try:
            modules_data = parse_modules_payload(data.pop('modules', None))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = CourseWriteSerializer(data=data)
        if not serializer.is_valid():
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with db_transaction.atomic():
                course = serializer.save(instructor=request.user, completion_tokens=10)
                logger.info(f"Course created: {course.id}")
                if modules_data is not None:
                    sync_course_content(course, modules_data)
                track_event(request, AnalyticsEvent.COURSE_UPLOADED, course=course)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(CourseListSerializer(course, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CourseUpdateView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def patch(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, instructor=request.user)
        except Course.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data.pop('completion_tokens', None)
        
        try:
            modules_data = parse_modules_payload(data.pop('modules', None))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = CourseWriteSerializer(course, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with db_transaction.atomic():
                serializer.save()
                if modules_data is not None:
                    sync_course_content(course, modules_data)
                    recalculate_course_enrollments(course)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(CourseListSerializer(course, context={'request': request}).data)


class CourseListView(generics.ListAPIView):
    serializer_class = CourseListSerializer
    permission_classes = (AllowAny,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('title', 'description', 'instructor__username')
    ordering_fields = ('created_at', 'price')

    def get_queryset(self):
        qs = Course.objects.filter(is_published=True).select_related('instructor', 'category')
        skill = self.request.query_params.get('skill_level')
        category = self.request.query_params.get('category')
        if skill:
            qs = qs.filter(skill_level=skill)
        if category:
            qs = qs.filter(category__slug=category)
        return qs

    def list(self, request, *args, **kwargs):
        search_term = request.query_params.get('search', '').strip()
        if search_term:
            track_event(request, AnalyticsEvent.SEARCH_USED, metadata={'query': search_term})
        return super().list(request, *args, **kwargs)

    def get_serializer_context(self):
        return {'request': self.request}


class EnrolledCourseDetailView(generics.RetrieveAPIView):
    """Course detail for enrolled learners — no is_published filter."""
    serializer_class = CourseDetailSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        course_id = self.kwargs['course_id']
        # Verify the user is actually enrolled
        enrollment = Enrollment.objects.filter(
            learner=self.request.user, course_id=course_id
        ).first()
        if not enrollment:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You are not enrolled in this course.')
        require_course_access(enrollment.course, self.request.user)
        return Course.objects.prefetch_related(
            'modules__lessons__quiz__questions__choices',
            'modules__assessments',
            'resources',
            'assessments',
            'reviews__learner',
        ).select_related('instructor', 'category').get(id=course_id)

    def get_serializer_context(self):
        return {'request': self.request}

    def retrieve(self, request, *args, **kwargs):
        course = self.get_object()
        track_event(request, AnalyticsEvent.COURSE_PAGE_VIEW, course=course)
        serializer = self.get_serializer(course)
        return Response(serializer.data)


class CourseDetailView(generics.RetrieveAPIView):
    queryset = Course.objects.filter(is_published=True).prefetch_related(
        'modules__lessons__quiz__questions__choices',
        'modules__assessments',
        'resources',
        'assessments',
        'reviews__learner',
    ).select_related('instructor', 'category')
    serializer_class = CourseDetailSerializer
    permission_classes = (AllowAny,)
    lookup_field = 'slug'

    def get_serializer_context(self):
        return {'request': self.request}

    def retrieve(self, request, *args, **kwargs):
        course = self.get_object()
        track_event(request, AnalyticsEvent.COURSE_PAGE_VIEW, course=course)
        serializer = self.get_serializer(course)
        return Response(serializer.data)


class LessonDetailView(generics.RetrieveAPIView):
    queryset = Lesson.objects.select_related('module__course', 'quiz').prefetch_related('quiz__questions__choices')
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        lesson = super().get_object()
        if not (lesson.is_free_preview and lesson.module.course.is_published):
            require_course_access(lesson.module.course, self.request.user)
        return lesson

    def get_serializer_context(self):
        return {'request': self.request}


# ── Enrollment ────────────────────────────────────────────────────────────────

class EnrollView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)

        enrollment, checkout, created = purchase_course(course, request.user, request.data.get('reference'))
        if checkout:
            return Response({'checkout': checkout}, status=status.HTTP_202_ACCEPTED)
        if not created:
            return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_200_OK)

        track_event(
            request,
            AnalyticsEvent.COURSE_PURCHASE_COMPLETED,
            course=course,
            metadata={'is_free': course.is_free, 'price': str(course.price)},
        )

        return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)


class MyEnrollmentsView(generics.ListAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Enrollment.objects.filter(
            learner=self.request.user
        ).filter(
            Q(course__is_free=True) | Q(payment__status='successful', payment__learner=self.request.user, payment__course_id=F('course_id'))
        ).select_related(
            'course__instructor', 'course__category'
        ).prefetch_related('lesson_progress')


# ── Progress ──────────────────────────────────────────────────────────────────

class CompleteLessonView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, lesson_id):
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            enrollment = Enrollment.objects.get(learner=request.user, course=lesson.module.course)
        except (Lesson.DoesNotExist, Enrollment.DoesNotExist):
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        require_course_access(enrollment.course, request.user)
        lp, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
        was_not_started = not LessonProgress.objects.filter(enrollment=enrollment, completed=True).exists()
        if not lp.completed:
            lp.completed = True
            lp.completed_at = timezone.now()
            lp.save()
            if was_not_started:
                track_event(request, AnalyticsEvent.COURSE_STARTED, course=enrollment.course)
            self._update_progress(enrollment)

        return Response(LessonProgressSerializer(lp).data)

    def _update_progress(self, enrollment):
        total_lessons = Lesson.objects.filter(module__course=enrollment.course).count()
        if total_lessons == 0:
            return
        completed = LessonProgress.objects.filter(enrollment=enrollment, completed=True).count()
        enrollment.progress_percent = round((completed / total_lessons) * 100)

        if enrollment.progress_percent >= 100:
            was_completed = enrollment.completed
            enrollment.completed = True
            if not was_completed:
                enrollment.completed_at = timezone.now()
                award_course_completion_tokens(enrollment)
                track_event(
                    self.request,
                    AnalyticsEvent.COURSE_COMPLETED,
                    user=enrollment.learner,
                    course=enrollment.course,
                )
        enrollment.save()


class CompleteModuleView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, module_id):
        try:
            module = Module.objects.get(id=module_id)
            enrollment = Enrollment.objects.get(learner=request.user, course=module.course)
        except (Module.DoesNotExist, Enrollment.DoesNotExist):
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        require_course_access(enrollment.course, request.user)
        mp, created = ModuleProgress.objects.get_or_create(enrollment=enrollment, module=module)

        if mp.completed and mp.reward_claimed:
            return Response({'detail': 'Module already completed and reward claimed.'}, status=status.HTTP_200_OK)

        if not mp.completed:
            mp.completed = True
            mp.completed_at = timezone.now()

        if not mp.reward_claimed:
            mp.reward_claimed = True
            wallet = award_tokens(
                enrollment.learner,
                module.reward_tokens,
                'module_complete',
                f'Completed module: {module.title}',
            )
            mp.save()
            return Response({
                'module_progress': ModuleProgressSerializer(mp).data,
                'tokens_awarded': module.reward_tokens,
                'new_balance': wallet.balance,
            })

        mp.save()
        return Response(ModuleProgressSerializer(mp).data)


# ── Reviews ───────────────────────────────────────────────────────────────────

class CourseReviewView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, is_published=True)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not Enrollment.objects.filter(learner=request.user, course=course).exists():
            return Response({'detail': 'You must be enrolled to review this course.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ReviewSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        review, created = Review.objects.update_or_create(
            course=course,
            learner=request.user,
            defaults=serializer.validated_data,
        )

        from django.db.models import Avg, Count
        stats = Review.objects.filter(course=course).aggregate(
            avg=Avg('rating'), total=Count('id')
        )
        response_data = ReviewSerializer(review, context={'request': request}).data
        response_data['average_rating'] = round(stats['avg'] or 0, 1)
        response_data['total_reviews'] = stats['total']
        return Response(response_data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# ── Token Wallet ──────────────────────────────────────────────────────────────

class MyWalletView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        wallet, _ = TokenWallet.objects.get_or_create(learner=request.user)
        return Response(TokenWalletSerializer(wallet).data)


class ClaimTokenView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, transaction_id):
        try:
            wallet = TokenWallet.objects.get(learner=request.user)
            tx = wallet.transactions.get(id=transaction_id, is_claimed=False)
        except (TokenWallet.DoesNotExist, TokenTransaction.DoesNotExist):
            return Response({'detail': 'Transaction not found or already claimed.'}, status=status.HTTP_404_NOT_FOUND)

        tx.is_claimed = True
        tx.save()
        wallet.balance += tx.amount
        wallet.save()
        return Response(TokenTransactionSerializer(tx).data)


# ── Learner Stats ─────────────────────────────────────────────────────────────

class MyStatsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        enrollments = Enrollment.objects.filter(learner=user)
        wallet, _ = TokenWallet.objects.get_or_create(learner=user)
        return Response({
            'courses_enrolled': enrollments.count(),
            'certificates_earned': enrollments.filter(completed=True).count(),
            'total_tokens': wallet.balance,
        })


# ── Educator Module / Lesson / Quiz / Assessment CRUD ────────────────────────

class ModuleCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, instructor=request.user)
        except Course.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        order = Module.objects.filter(course=course).count() + 1
        module = Module.objects.create(course=course, title=request.data.get('title', ''), order=order)
        return Response(ModuleSerializer(module, context={'request': request}).data, status=201)


class ModuleUpdateView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, module_id):
        try:
            module = Module.objects.get(id=module_id, course__instructor=request.user)
        except Module.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        module.title = request.data.get('title', module.title)
        module.save()
        return Response(ModuleSerializer(module, context={'request': request}).data)

    def delete(self, request, module_id):
        try:
            module = Module.objects.get(id=module_id, course__instructor=request.user)
        except Module.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        module.delete()
        return Response(status=204)


class LessonCreateView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def post(self, request, module_id):
        try:
            module = Module.objects.get(id=module_id, course__instructor=request.user)
        except Module.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        order = Lesson.objects.filter(module=module).count() + 1
        lesson = Lesson.objects.create(
            module=module,
            title=request.data.get('title', ''),
            lesson_type=request.data.get('lesson_type', 'video'),
            order=order,
            duration_minutes=int(request.data.get('duration_minutes', 0)),
            content=request.data.get('content', ''),
            is_free_preview=str(request.data.get('is_free_preview', 'false')).lower() == 'true',
        )
        if 'video_file' in request.FILES:
            lesson.video_file = request.FILES['video_file']
            lesson.save()
        return Response(LessonSerializer(lesson, context={'request': request}).data, status=201)


class LessonUpdateView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get(self, request, lesson_id):
        try:
            lesson = Lesson.objects.select_related('module__course').prefetch_related('quiz__questions__choices').get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        if not (lesson.is_free_preview and lesson.module.course.is_published):
            require_course_access(lesson.module.course, request.user)
        return Response(LessonSerializer(lesson, context={'request': request}).data)

    def patch(self, request, lesson_id):
        try:
            lesson = Lesson.objects.get(id=lesson_id, module__course__instructor=request.user)
        except Lesson.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        for field in ('title', 'lesson_type', 'content', 'duration_minutes'):
            if field in request.data:
                setattr(lesson, field, request.data[field])
        if 'video_file' in request.FILES:
            if lesson.video_file:
                lesson.video_file.delete(save=False)
            lesson.video_file = request.FILES['video_file']
        if 'is_free_preview' in request.data:
            lesson.is_free_preview = str(request.data['is_free_preview']).lower() == 'true'
        lesson.save()
        return Response(LessonSerializer(lesson, context={'request': request}).data)

    def delete(self, request, lesson_id):
        try:
            lesson = Lesson.objects.get(id=lesson_id, module__course__instructor=request.user)
        except Lesson.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        lesson.delete()
        return Response(status=204)


class QuizCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, module_id):
        try:
            module = Module.objects.get(id=module_id, course__instructor=request.user)
        except Module.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        if hasattr(module, 'quiz'):
            return Response({'detail': 'Quiz already exists for this module.'}, status=400)
        quiz = Quiz.objects.create(
            module=module,
            title=request.data.get('title', f'{module.title} Quiz'),
            pass_score=int(request.data.get('pass_score', 70)),
        )
        questions_data = request.data.get('questions', [])
        for q_data in questions_data:
            question = Question.objects.create(quiz=quiz, text=q_data.get('text', ''), order=q_data.get('order', 0))
            for c_data in q_data.get('choices', []):
                Choice.objects.create(question=question, text=c_data.get('text', ''), is_correct=c_data.get('is_correct', False))
        return Response(QuizSerializer(quiz).data, status=201)


class QuizUpdateView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, quiz_id):
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            quiz = Quiz.objects.get(id=quiz_id, module__course__instructor=request.user)
        except Quiz.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        
        # Update quiz fields
        quiz.title = request.data.get('title', quiz.title)
        quiz.pass_score = int(request.data.get('pass_score', quiz.pass_score))
        quiz.reward_tokens = int(request.data.get('reward_tokens', quiz.reward_tokens))
        quiz.save()
        
        # Update questions if provided
        questions_data = request.data.get('questions', [])
        if questions_data:
            logger.info(f"Updating {len(questions_data)} questions for quiz {quiz_id}")
            
            # Delete existing questions (cascade will delete choices)
            quiz.questions.all().delete()
            
            # Create new questions
            for q_data in questions_data:
                question = Question.objects.create(
                    quiz=quiz,
                    text=q_data.get('text', ''),
                    order=q_data.get('order', 0)
                )
                logger.info(f"Created question: {question.id}")
                
                # Create choices
                for c_data in q_data.get('choices', []):
                    choice = Choice.objects.create(
                        question=question,
                        text=c_data.get('text', ''),
                        is_correct=c_data.get('is_correct', False)
                    )
                    logger.info(f"Created choice: {choice.id} - correct={choice.is_correct}")
        
        return Response(QuizSerializer(quiz).data)

    def delete(self, request, quiz_id):
        try:
            quiz = Quiz.objects.get(id=quiz_id, module__course__instructor=request.user)
        except Quiz.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        quiz.delete()
        return Response(status=204)


class AssessmentCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, instructor=request.user)
        except Course.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        assessment = Assessment.objects.create(
            course=course,
            title=request.data.get('title', ''),
            description=request.data.get('description', ''),
            assessment_type=request.data.get('assessment_type', 'graded'),
            duration_minutes=int(request.data.get('duration_minutes', 20)),
            due_date=request.data.get('due_date') or None,
        )
        return Response(AssessmentSerializer(assessment).data, status=201)


class AssessmentUpdateView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, assessment_id):
        try:
            assessment = Assessment.objects.get(id=assessment_id, course__instructor=request.user)
        except Assessment.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        for field in ('title', 'description', 'assessment_type', 'duration_minutes', 'due_date'):
            if field in request.data:
                setattr(assessment, field, request.data[field] or None if field == 'due_date' else request.data[field])
        assessment.save()
        return Response(AssessmentSerializer(assessment).data)

    def delete(self, request, assessment_id):
        try:
            assessment = Assessment.objects.get(id=assessment_id, course__instructor=request.user)
        except Assessment.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        assessment.delete()
        return Response(status=204)


class CourseContentView(APIView):
    """Returns full module/lesson/quiz/assessment structure for an educator's course."""
    permission_classes = (IsAuthenticated,)

    def get(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, instructor=request.user)
        except Course.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        modules = Module.objects.filter(course=course).prefetch_related('lessons__quiz__questions__choices')
        assessments = Assessment.objects.filter(course=course)
        return Response({
            'modules': ModuleSerializer(modules, many=True, context={'request': request}).data,
            'assessments': AssessmentSerializer(assessments, many=True).data,
        })


# ── Certificates ──────────────────────────────────────────────────────────────

class IssueCertificateView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, enrollment_id):
        try:
            enrollment = Enrollment.objects.get(id=enrollment_id, learner=request.user)
        except Enrollment.DoesNotExist:
            return Response({'detail': 'Enrollment not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not enrollment.completed:
            return Response({'detail': 'Course not completed yet.'}, status=status.HTTP_400_BAD_REQUEST)

        if hasattr(enrollment, 'certificate'):
            return Response(
                CertificateSerializer(enrollment.certificate, context={'request': request}).data,
                status=status.HTTP_200_OK,
            )

        cert_type = request.data.get('cert_type', 'standard')
        if cert_type not in ('standard', 'nft'):
            return Response({'detail': 'cert_type must be "standard" or "nft".'}, status=status.HTTP_400_BAD_REQUEST)

        cert = Certificate.objects.create(enrollment=enrollment, cert_type=cert_type)

        # Generate PDF certificate
        if cert_type == 'standard':
            from .utils import generate_certificate_pdf
            generate_certificate_pdf(cert)
        
        # Refresh from database to ensure certificate_id is populated
        cert.refresh_from_db()
        
        return Response(
            CertificateSerializer(cert, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class RegenerateCertificateView(APIView):
    """Force regenerate the PDF for an existing certificate."""
    permission_classes = (IsAuthenticated,)

    def post(self, request, certificate_id):
        try:
            cert = Certificate.objects.get(
                certificate_id=certificate_id,
                enrollment__learner=request.user,
                cert_type='standard',
            )
        except Certificate.DoesNotExist:
            return Response({'detail': 'Certificate not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Delete old files
        if cert.pdf_file:
            cert.pdf_file.delete(save=False)
            cert.pdf_file = None
        if cert.qr_code:
            cert.qr_code.delete(save=False)
            cert.qr_code = None
        cert.save()

        from .utils import generate_certificate_pdf
        generate_certificate_pdf(cert)

        return Response(
            CertificateSerializer(cert, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )


class MyCertificatesView(generics.ListAPIView):
    serializer_class = CertificateSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Certificate.objects.filter(
            enrollment__learner=self.request.user
        ).select_related('enrollment__course__instructor', 'enrollment__learner')

    def get_serializer_context(self):
        return {'request': self.request}


class CertificateDetailView(APIView):
    """View a specific certificate by certificate_id (alphanumeric)."""
    permission_classes = [AllowAny]

    def get(self, request, certificate_id):
        try:
            certificate = Certificate.objects.select_related(
                'enrollment__course__instructor', 
                'enrollment__learner'
            ).get(certificate_id=certificate_id)
        except Certificate.DoesNotExist:
            return Response({'detail': 'Certificate not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(CertificateSerializer(certificate, context={'request': request}).data)


# ── Sessions ──────────────────────────────────────────────────────────────────

class SessionListCreateView(APIView):
    """List all sessions for instructor or create a new session."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        sessions = Session.objects.filter(instructor=request.user).select_related('course').prefetch_related('registrations')
        serializer = SessionSerializer(sessions, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = SessionSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(instructor=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SessionDetailView(APIView):
    """Retrieve, update, or delete a session."""
    permission_classes = (IsAuthenticated,)

    def get(self, request, session_id):
        try:
            session = Session.objects.select_related('course').prefetch_related('registrations__learner').get(
                id=session_id, instructor=request.user
            )
        except Session.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SessionSerializer(session, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id, instructor=request.user)
        except Session.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SessionSerializer(session, data=request.data, partial=True, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id, instructor=request.user)
        except Session.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicSessionListView(generics.ListAPIView):
    """List all upcoming sessions (for learners)."""
    serializer_class = SessionSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        from django.utils import timezone
        return Session.objects.filter(
            status='scheduled',
            scheduled_date__gte=timezone.now().date()
        ).select_related('instructor', 'course').prefetch_related('registrations')

    def get_serializer_context(self):
        return {'request': self.request}


class SessionRegisterView(APIView):
    """Register for a session."""
    permission_classes = (IsAuthenticated,)

    def post(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id, status='scheduled')
        except Session.DoesNotExist:
            return Response({'detail': 'Session not found or not available.'}, status=status.HTTP_404_NOT_FOUND)

        # Check if already registered
        if SessionRegistration.objects.filter(session=session, learner=request.user).exists():
            return Response({'detail': 'Already registered.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check max participants
        if session.max_participants > 0:
            current_count = session.registrations.count()
            if current_count >= session.max_participants:
                return Response({'detail': 'Session is full.'}, status=status.HTTP_400_BAD_REQUEST)

        registration = SessionRegistration.objects.create(session=session, learner=request.user)
        return Response(SessionRegistrationSerializer(registration).data, status=status.HTTP_201_CREATED)


class SessionUnregisterView(APIView):
    """Unregister from a session."""
    permission_classes = (IsAuthenticated,)

    def delete(self, request, session_id):
        try:
            registration = SessionRegistration.objects.get(session_id=session_id, learner=request.user)
        except SessionRegistration.DoesNotExist:
            return Response({'detail': 'Not registered.'}, status=status.HTTP_404_NOT_FOUND)
        registration.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Educator Wallet ───────────────────────────────────────────────────────────

class EducatorWalletView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        # Only educators have a wallet
        if not hasattr(request.user, 'profile') or request.user.profile.role != 'educator':
            return Response({'detail': 'Only educators have a wallet.'}, status=status.HTTP_403_FORBIDDEN)
        wallet, _ = EducatorWallet.objects.get_or_create(educator=request.user)
        transactions = wallet.transactions.all()[:20]
        token_wallet, _ = TokenWallet.objects.get_or_create(learner=request.user)
        token_transactions = token_wallet.transactions.order_by('-created_at')[:20]
        pending_token_balance = sum(
            token_wallet.transactions.filter(is_claimed=False).values_list('amount', flat=True)
        )
        total_courses = Course.objects.filter(instructor=request.user).count()
        total_students = Enrollment.objects.filter(course__instructor=request.user).values('learner').distinct().count()
        return Response({
            'balance': str(wallet.balance),
            'total_earned': str(wallet.total_earned),
            'total_withdrawn': str(wallet.total_withdrawn),
            'total_courses': total_courses,
            'total_students': total_students,
            'token_balance': token_wallet.balance,
            'pending_token_balance': pending_token_balance,
            'total_token_earned': token_wallet.balance + pending_token_balance,
            'token_transactions': [
                {
                    'id': t.id,
                    'amount': t.amount,
                    'reason': t.reason,
                    'description': t.description,
                    'created_at': t.created_at,
                    'is_claimed': t.is_claimed,
                }
                for t in token_transactions
            ],
            'transactions': [
                {
                    'id': t.id,
                    'amount': str(t.amount),
                    'type': t.transaction_type,
                    'description': t.description,
                    'course': t.course.title if t.course else None,
                    'created_at': t.created_at,
                }
                for t in transactions
            ],
        })


class WithdrawalRequestView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        wallet, _ = EducatorWallet.objects.get_or_create(educator=request.user)
        withdrawals = wallet.withdrawals.all()[:10]
        return Response([
            {
                'id': w.id,
                'amount': str(w.amount),
                'bank_name': w.bank_name,
                'account_number': w.account_number,
                'account_name': w.account_name,
                'status': w.status,
                'created_at': w.created_at,
            }
            for w in withdrawals
        ])

    def post(self, request):
        from decimal import Decimal, InvalidOperation

        # Only educators can withdraw
        if not hasattr(request.user, 'profile') or request.user.profile.role != 'educator':
            return Response({'detail': 'Only educators can withdraw.'}, status=status.HTTP_403_FORBIDDEN)

        wallet, _ = EducatorWallet.objects.get_or_create(educator=request.user)

        try:
            amount = Decimal(str(request.data.get('amount', '0'))).quantize(Decimal('0.01'))
        except InvalidOperation:
            return Response({'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)

        bank_name = request.data.get('bank_name', '').strip()
        account_number = request.data.get('account_number', '').strip()
        account_name = request.data.get('account_name', '').strip()

        if not all([bank_name, account_number, account_name]):
            return Response({'detail': 'Bank name, account number and account name are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({'detail': 'Amount must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount > wallet.balance:
            return Response({'detail': f'Insufficient balance. Available: ₦{wallet.balance}'}, status=status.HTTP_400_BAD_REQUEST)

        # Deduct from wallet immediately and create withdrawal request
        wallet.balance = Decimal(str(wallet.balance)) - amount
        wallet.total_withdrawn = Decimal(str(wallet.total_withdrawn)) + amount
        wallet.save()

        EducatorTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            transaction_type='debit',
            description=f'Withdrawal request to {bank_name} — {account_number}',
        )

        withdrawal = WithdrawalRequest.objects.create(
            wallet=wallet,
            amount=amount,
            bank_name=bank_name,
            account_number=account_number,
            account_name=account_name,
        )

        return Response({
            'id': withdrawal.id,
            'amount': str(withdrawal.amount),
            'status': withdrawal.status,
            'message': 'Withdrawal request submitted. You will receive your money in 1-2 business working days.',
        }, status=status.HTTP_201_CREATED)

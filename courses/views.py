from django.utils import timezone
from rest_framework import status, generics, filters, parsers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import json
import re

from .models import (
    Category, Course, Module, Lesson, Enrollment, LessonProgress,
    ModuleProgress, Review, TokenWallet, TokenTransaction, Assessment,
    Certificate, Quiz, Question, Choice, Session, SessionRegistration,
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
                video_url=lesson_data.get('videoUrl', ''),
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


# ── Categories ────────────────────────────────────────────────────────────────

class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (AllowAny,)


# ── Courses ───────────────────────────────────────────────────────────────────

class EducatorCourseListView(generics.ListAPIView):
    """Returns all courses (published + draft) created by the authenticated educator."""
    serializer_class = CourseWriteSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Course.objects.filter(instructor=self.request.user).select_related('instructor', 'category')


class CourseCreateView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def post(self, request):
        from django.utils.text import slugify
        import uuid
        import logging
        logger = logging.getLogger(__name__)
        
        data = request.data.copy()
        logger.info(f"Received data keys: {data.keys()}")
        
        base_slug = slugify(data.get('title', ''))[:50] or 'course'
        slug = base_slug
        if Course.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{uuid.uuid4().hex[:6]}'
        data['slug'] = slug
        data['completion_tokens'] = 10
        
        # Extract modules data
        modules_json = data.pop('modules', None)
        modules_data = []
        
        logger.info(f"Modules JSON type: {type(modules_json)}")
        logger.info(f"Modules JSON value: {repr(modules_json)[:200]}")
        
        if modules_json:
            if isinstance(modules_json, str):
                try:
                    # First parse
                    parsed = json.loads(modules_json)
                    logger.info(f"First parse type: {type(parsed)}")
                    
                    # Check if it's a string that needs another parse (double-encoded)
                    if isinstance(parsed, str):
                        logger.info("Double-encoded JSON detected, parsing again")
                        modules_data = json.loads(parsed)
                    else:
                        modules_data = parsed
                    
                    logger.info(f"Final parsed modules type: {type(modules_data)}")
                    logger.info(f"Parsed modules: {len(modules_data)} modules")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {str(e)}")
                    modules_data = []
            elif isinstance(modules_json, list):
                modules_data = modules_json
                logger.info(f"Modules already list: {len(modules_data)} modules")
        
        serializer = CourseWriteSerializer(data=data)
        if not serializer.is_valid():
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        course = serializer.save(instructor=request.user, completion_tokens=10)
        logger.info(f"Course created: {course.id}")
        
        # Create modules, lessons, quizzes, and assessments
        if modules_data:
            logger.info(f"Creating content for {len(modules_data)} modules")
            create_course_content(course, modules_data)
        else:
            logger.warning("No modules data to create")
        
        return Response(CourseListSerializer(course, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CourseUpdateView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def patch(self, request, course_id):
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            course = Course.objects.get(id=course_id, instructor=request.user)
        except Course.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data.pop('completion_tokens', None)
        
        # Extract modules data
        modules_json = data.pop('modules', None)
        modules_data = None
        
        logger.info(f"Modules JSON type: {type(modules_json)}")
        logger.info(f"Modules JSON value: {repr(modules_json)[:200]}")
        
        if modules_json:
            if isinstance(modules_json, str):
                try:
                    # First parse
                    parsed = json.loads(modules_json)
                    logger.info(f"First parse type: {type(parsed)}")
                    
                    # Check if it's a string that needs another parse (double-encoded)
                    if isinstance(parsed, str):
                        logger.info("Double-encoded JSON detected, parsing again")
                        modules_data = json.loads(parsed)
                    else:
                        modules_data = parsed
                    
                    logger.info(f"Final parsed modules type: {type(modules_data)}")
                    logger.info(f"Parsed modules count: {len(modules_data) if isinstance(modules_data, list) else 'not a list'}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {str(e)}")
                    return Response({'detail': f'Invalid JSON in modules: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
            elif isinstance(modules_json, list):
                modules_data = modules_json
                logger.info(f"Modules data is already a list: {len(modules_data)} modules")
            else:
                logger.error(f"Modules is neither string nor list: {type(modules_json)}")
                return Response({'detail': 'Modules must be a JSON string or list'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = CourseWriteSerializer(course, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        
        # Update modules if provided
        if modules_data:
            logger.info(f"Creating course content with {len(modules_data)} modules")
            course.modules.all().delete()
            create_course_content(course, modules_data)
        
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


class LessonDetailView(generics.RetrieveAPIView):
    queryset = Lesson.objects.select_related('module__course', 'quiz').prefetch_related('quiz__questions__choices')
    serializer_class = LessonSerializer
    permission_classes = (IsAuthenticated,)


# ── Enrollment ────────────────────────────────────────────────────────────────

class EnrollView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id, is_published=True)
        except Course.DoesNotExist:
            return Response({'detail': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)

        enrollment, created = Enrollment.objects.get_or_create(learner=request.user, course=course)
        if not created:
            return Response({'detail': 'Already enrolled.'}, status=status.HTTP_200_OK)

        return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)


class MyEnrollmentsView(generics.ListAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Enrollment.objects.filter(learner=self.request.user).select_related('course')


# ── Progress ──────────────────────────────────────────────────────────────────

class CompleteLessonView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, lesson_id):
        try:
            lesson = Lesson.objects.get(id=lesson_id)
            enrollment = Enrollment.objects.get(learner=request.user, course=lesson.module.course)
        except (Lesson.DoesNotExist, Enrollment.DoesNotExist):
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        lp, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
        if not lp.completed:
            lp.completed = True
            lp.completed_at = timezone.now()
            lp.save()
            self._update_progress(enrollment)

        return Response(LessonProgressSerializer(lp).data)

    def _update_progress(self, enrollment):
        total_lessons = Lesson.objects.filter(module__course=enrollment.course).count()
        if total_lessons == 0:
            return
        completed = LessonProgress.objects.filter(enrollment=enrollment, completed=True).count()
        enrollment.progress_percent = round((completed / total_lessons) * 100)

        if enrollment.progress_percent >= 100:
            enrollment.completed = True
            enrollment.completed_at = timezone.now()
            award_tokens(
                enrollment.learner,
                enrollment.course.completion_tokens,
                'course_complete',
                f'Completed course: {enrollment.course.title}',
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
        return Response(ModuleSerializer(module).data, status=201)


class ModuleUpdateView(APIView):
    permission_classes = (IsAuthenticated,)

    def patch(self, request, module_id):
        try:
            module = Module.objects.get(id=module_id, course__instructor=request.user)
        except Module.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        module.title = request.data.get('title', module.title)
        module.save()
        return Response(ModuleSerializer(module).data)

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
            video_url=request.data.get('video_url', ''),
            content=request.data.get('content', ''),
            is_free_preview=str(request.data.get('is_free_preview', 'false')).lower() == 'true',
        )
        return Response(LessonSerializer(lesson).data, status=201)


class LessonUpdateView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def patch(self, request, lesson_id):
        try:
            lesson = Lesson.objects.get(id=lesson_id, module__course__instructor=request.user)
        except Lesson.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        for field in ('title', 'lesson_type', 'video_url', 'content', 'duration_minutes'):
            if field in request.data:
                setattr(lesson, field, request.data[field])
        if 'is_free_preview' in request.data:
            lesson.is_free_preview = str(request.data['is_free_preview']).lower() == 'true'
        lesson.save()
        return Response(LessonSerializer(lesson).data)

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
            'modules': ModuleSerializer(modules, many=True).data,
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
        
        return Response(
            CertificateSerializer(cert, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class MyCertificatesView(generics.ListAPIView):
    serializer_class = CertificateSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Certificate.objects.filter(
            enrollment__learner=self.request.user
        ).select_related('enrollment__course', 'enrollment__learner')

    def get_serializer_context(self):
        return {'request': self.request}


class CertificateDetailView(APIView):
    """View a specific certificate."""
    permission_classes = (IsAuthenticated,)

    def get(self, request, certificate_id):
        try:
            certificate = Certificate.objects.select_related('enrollment__course', 'enrollment__learner').get(
                id=certificate_id, enrollment__learner=request.user
            )
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

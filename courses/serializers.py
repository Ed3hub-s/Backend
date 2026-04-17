from django.utils import timezone
from rest_framework import serializers
from .models import (
    Category, Course, Module, Lesson, Quiz, Question, Choice,
    Assessment, CourseResource, Enrollment, LessonProgress,
    ModuleProgress, Review, TokenWallet, TokenTransaction, Certificate,
    Session, SessionRegistration,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug')


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ('id', 'text', 'is_correct')


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ('id', 'text', 'order', 'choices')


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = ('id', 'title', 'pass_score', 'reward_tokens', 'questions')


class LessonSerializer(serializers.ModelSerializer):
    quiz = QuizSerializer(read_only=True)
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = (
            'id', 'title', 'lesson_type', 'order', 'duration_minutes',
            'video_url', 'content', 'transcript', 'is_free_preview', 'quiz',
        )

    def get_video_url(self, obj):
        if obj.video_file:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.video_file.url) if request else obj.video_file.url
        return None


class AssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = ('id', 'title', 'description', 'assessment_type', 'duration_minutes', 'due_date', 'reward_tokens')


class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    assessments = AssessmentSerializer(many=True, read_only=True)
    quiz = QuizSerializer(read_only=True)

    class Meta:
        model = Module
        fields = ('id', 'title', 'order', 'reward_tokens', 'lessons', 'assessments', 'quiz')


class CourseResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseResource
        fields = ('id', 'title', 'resource_type', 'url', 'file', 'description')


class ReviewSerializer(serializers.ModelSerializer):
    learner_name = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ('id', 'learner_name', 'rating', 'comment', 'created_at', 'is_mine')
        read_only_fields = ('id', 'learner_name', 'created_at', 'is_mine')

    def get_learner_name(self, obj):
        full = f'{obj.learner.first_name} {obj.learner.last_name}'.strip()
        return full or obj.learner.username

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.learner_id == request.user.id
        return False


class CourseWriteSerializer(serializers.ModelSerializer):
    """Used for create/update by educators."""
    class Meta:
        model = Course
        fields = (
            'id', 'title', 'slug', 'description', 'thumbnail', 'skill_level',
            'price', 'is_free', 'is_published',
            'duration_weeks', 'estimated_hours', 'hours_per_week', 'is_self_paced',
            'tools_used', 'ideal_for', 'what_included', 'what_you_learn',
            'completion_tokens',
        )
        read_only_fields = ('id', 'slug', 'completion_tokens')


class CourseListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    instructor_name = serializers.SerializerMethodField()
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    total_enrolled = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = (
            'id', 'title', 'slug', 'thumbnail', 'skill_level', 'price', 'is_free',
            'instructor_name', 'average_rating', 'total_reviews', 'total_enrolled',
            'category_name', 'estimated_hours', 'is_published',
        )

    def get_instructor_name(self, obj):
        full = f'{obj.instructor.first_name} {obj.instructor.last_name}'.strip()
        return full or obj.instructor.username

    def get_thumbnail(self, obj):
        if obj.thumbnail:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.thumbnail.url) if request else obj.thumbnail.url
        return None


class CourseDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail view."""
    instructor_name = serializers.SerializerMethodField()
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    total_enrolled = serializers.IntegerField(read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    resources = CourseResourceSerializer(many=True, read_only=True)
    assessments = AssessmentSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    category = CategorySerializer(read_only=True)
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = (
            'id', 'title', 'slug', 'description', 'thumbnail', 'skill_level',
            'price', 'is_free', 'is_published', 'instructor_name', 'category',
            'duration_weeks', 'estimated_hours', 'hours_per_week', 'is_self_paced',
            'tools_used', 'ideal_for', 'what_included', 'what_you_learn', 'certificate_url',
            'completion_tokens', 'average_rating', 'total_reviews', 'total_enrolled',
            'modules', 'resources', 'assessments', 'reviews',
            'created_at', 'updated_at',
        )

    def get_instructor_name(self, obj):
        full = f'{obj.instructor.first_name} {obj.instructor.last_name}'.strip()
        return full or obj.instructor.username

    def get_thumbnail(self, obj):
        if obj.thumbnail:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.thumbnail.url) if request else obj.thumbnail.url
        return None


class LessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = ('id', 'lesson', 'completed', 'completed_at')


class ModuleProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleProgress
        fields = ('id', 'module', 'completed', 'completed_at', 'reward_claimed')


class EnrollmentSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)
    lesson_progress = LessonProgressSerializer(many=True, read_only=True)
    certificate_id = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = ('id', 'course', 'enrolled_at', 'completed', 'completed_at', 'progress_percent', 'lesson_progress', 'certificate_id')

    def get_certificate_id(self, obj):
        try:
            return obj.certificate.certificate_id
        except Exception:
            return None


class TokenTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TokenTransaction
        fields = ('id', 'amount', 'reason', 'description', 'created_at', 'is_claimed')


class TokenWalletSerializer(serializers.ModelSerializer):
    transactions = TokenTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = TokenWallet
        fields = ('id', 'balance', 'updated_at', 'transactions')


class CertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='enrollment.course.title', read_only=True)
    course_slug = serializers.CharField(source='enrollment.course.slug', read_only=True)
    learner_name = serializers.SerializerMethodField()
    instructor_name = serializers.SerializerMethodField()
    pdf_url = serializers.SerializerMethodField()
    qr_code_url = serializers.SerializerMethodField()
    verify_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            'id', 'certificate_id', 'cert_type', 'issued_at', 
            'course_title', 'course_slug', 'learner_name', 'instructor_name', 
            'pdf_url', 'qr_code_url', 'verify_url', 'nft_tx_hash'
        )

    def get_learner_name(self, obj):
        u = obj.enrollment.learner
        return f'{u.first_name} {u.last_name}'.strip() or u.username

    def get_instructor_name(self, obj):
        u = obj.enrollment.course.instructor
        full = f'{u.first_name} {u.last_name}'.strip()
        return full if full else u.username

    def get_pdf_url(self, obj):
        if obj.pdf_file:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.pdf_file.url) if request else obj.pdf_file.url
        return None

    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.qr_code.url) if request else obj.qr_code.url
        return None

    def get_verify_url(self, obj):
        from django.conf import settings
        frontend_url = getattr(settings, 'FRONTEND_URL', 'https://ed3hub.com').rstrip('/')
        return f'{frontend_url}/certificate/verify/{obj.certificate_id}'


class SessionRegistrationSerializer(serializers.ModelSerializer):
    learner_name = serializers.SerializerMethodField()
    learner_email = serializers.EmailField(source='learner.email', read_only=True)

    class Meta:
        model = SessionRegistration
        fields = ('id', 'learner', 'learner_name', 'learner_email', 'registered_at', 'attended')
        read_only_fields = ('id', 'registered_at')

    def get_learner_name(self, obj):
        u = obj.learner
        return f'{u.first_name} {u.last_name}'.strip() or u.username


class SessionSerializer(serializers.ModelSerializer):
    instructor_name = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    registrations_count = serializers.SerializerMethodField()
    is_registered = serializers.SerializerMethodField()
    registrations = SessionRegistrationSerializer(many=True, read_only=True)

    class Meta:
        model = Session
        fields = (
            'id', 'instructor', 'instructor_name', 'course', 'course_title',
            'title', 'description', 'session_type', 'status',
            'scheduled_date', 'scheduled_time', 'duration_minutes',
            'meeting_link', 'meeting_platform', 'max_participants',
            'registrations_count', 'is_registered', 'registrations',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'instructor', 'created_at', 'updated_at')

    def get_instructor_name(self, obj):
        u = obj.instructor
        return f'{u.first_name} {u.last_name}'.strip() or u.username

    def get_registrations_count(self, obj):
        return obj.registrations.count()

    def get_is_registered(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.registrations.filter(learner=request.user).exists()
        return False

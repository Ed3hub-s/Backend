from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from .models import (
    Category, Course, Module, Lesson, Quiz, Question, Choice,
    Assessment, CourseResource, Enrollment, LessonProgress,
    ModuleProgress, Review, TokenWallet, TokenTransaction, Certificate,
    Session, SessionRegistration, EducatorWallet, EducatorTransaction, WithdrawalRequest
)


class ChoiceInline(TabularInline):
    model = Choice
    extra = 4


class QuestionInline(StackedInline):
    model = Question
    extra = 2


class LessonInline(TabularInline):
    model = Lesson
    extra = 1
    fields = ('title', 'lesson_type', 'order', 'duration_minutes', 'video_file', 'content', 'is_free_preview')


class ModuleInline(TabularInline):
    model = Module
    extra = 1


@admin.register(Quiz)
class QuizAdmin(ModelAdmin):
    list_display = ('title', 'get_module', 'get_lesson', 'pass_score', 'reward_tokens')
    list_filter = ('pass_score',)
    search_fields = ('title', 'module__title', 'lesson__title')
    inlines = [QuestionInline]
    
    def get_module(self, obj):
        return obj.module.title if obj.module else '-'
    get_module.short_description = 'Module'
    
    def get_lesson(self, obj):
        return obj.lesson.title if obj.lesson else '-'
    get_lesson.short_description = 'Lesson'


@admin.register(Question)
class QuestionAdmin(ModelAdmin):
    list_display = ('get_text_preview', 'quiz', 'order', 'get_choices_count')
    list_filter = ('quiz',)
    search_fields = ('text',)
    inlines = [ChoiceInline]
    
    def get_text_preview(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    get_text_preview.short_description = 'Question'
    
    def get_choices_count(self, obj):
        return obj.choices.count()
    get_choices_count.short_description = 'Choices'


@admin.register(Choice)
class ChoiceAdmin(ModelAdmin):
    list_display = ('text', 'question', 'is_correct')
    list_filter = ('is_correct',)
    search_fields = ('text', 'question__text')


@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display = ('title', 'instructor', 'skill_level', 'is_published', 'price', 'created_at')
    list_filter = ('skill_level', 'is_published', 'category')
    search_fields = ('title', 'instructor__username')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(ModelAdmin):
    list_display = ('title', 'course', 'order', 'reward_tokens')
    inlines = [LessonInline]


@admin.register(Enrollment)
class EnrollmentAdmin(ModelAdmin):
    list_display = ('learner', 'course', 'progress_percent', 'completed', 'enrolled_at')


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ('learner', 'course', 'rating', 'created_at')


@admin.register(TokenWallet)
class TokenWalletAdmin(ModelAdmin):
    list_display = ('learner', 'balance', 'updated_at')


@admin.register(TokenTransaction)
class TokenTransactionAdmin(ModelAdmin):
    list_display = ('wallet', 'amount', 'reason', 'is_claimed', 'created_at')


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    search_fields = ('name',)


@admin.register(Lesson)
class LessonAdmin(ModelAdmin):
    list_display = ('title', 'module', 'lesson_type', 'order', 'duration_minutes')
    list_filter = ('lesson_type',)
    search_fields = ('title', 'module__title')
    fields = ('module', 'title', 'lesson_type', 'order', 'duration_minutes', 'video_file', 'content', 'transcript', 'is_free_preview')


@admin.register(Assessment)
class AssessmentAdmin(ModelAdmin):
    list_display = ('title', 'course', 'get_module', 'assessment_type', 'duration_minutes', 'reward_tokens')
    list_filter = ('assessment_type', 'course')
    search_fields = ('title', 'description', 'course__title')
    
    def get_module(self, obj):
        return obj.module.title if obj.module else '-'
    get_module.short_description = 'Module'


@admin.register(CourseResource)
class CourseResourceAdmin(ModelAdmin):
    list_display = ('title', 'course', 'resource_type')


@admin.register(LessonProgress)
class LessonProgressAdmin(ModelAdmin):
    list_display = ('enrollment', 'lesson', 'completed')


@admin.register(ModuleProgress)
class ModuleProgressAdmin(ModelAdmin):
    list_display = ('enrollment', 'module', 'completed')


@admin.register(Certificate)
class CertificateAdmin(ModelAdmin):
    list_display = ('certificate_id', 'get_learner', 'get_course', 'cert_type', 'issued_at')
    list_filter = ('cert_type', 'issued_at')
    search_fields = ('certificate_id', 'enrollment__learner__username', 'enrollment__course__title')
    readonly_fields = ('issued_at', 'get_pdf_link', 'get_qr_link')
    fields = ('certificate_id', 'enrollment', 'cert_type', 'issued_at', 'pdf_file', 'get_pdf_link', 'qr_code', 'get_qr_link', 'nft_tx_hash')
    
    def get_learner(self, obj):
        return obj.enrollment.learner.username
    get_learner.short_description = 'Learner'
    
    def get_course(self, obj):
        return obj.enrollment.course.title
    get_course.short_description = 'Course'
    
    def get_pdf_link(self, obj):
        if obj.pdf_file:
            return f'<a href="{obj.pdf_file.url}" target="_blank">Download PDF</a>'
        return '-'
    get_pdf_link.short_description = 'PDF Download'
    get_pdf_link.allow_tags = True
    
    def get_qr_link(self, obj):
        if obj.qr_code:
            return f'<a href="{obj.qr_code.url}" target="_blank">View QR Code</a>'
        return '-'
    get_qr_link.short_description = 'QR Code'
    get_qr_link.allow_tags = True


class SessionRegistrationInline(TabularInline):
    model = SessionRegistration
    extra = 0
    readonly_fields = ('registered_at',)


@admin.register(Session)
class SessionAdmin(ModelAdmin):
    list_display = ('title', 'instructor', 'get_course', 'session_type', 'status', 'scheduled_date', 'scheduled_time', 'get_registrations_count')
    list_filter = ('session_type', 'status', 'scheduled_date')
    search_fields = ('title', 'instructor__username', 'course__title')
    inlines = [SessionRegistrationInline]
    
    def get_course(self, obj):
        return obj.course.title if obj.course else '-'
    get_course.short_description = 'Course'
    
    def get_registrations_count(self, obj):
        return obj.registrations.count()
    get_registrations_count.short_description = 'Registrations'


@admin.register(SessionRegistration)
class SessionRegistrationAdmin(ModelAdmin):
    list_display = ('learner', 'session', 'registered_at', 'attended')
    list_filter = ('attended', 'registered_at')
    search_fields = ('learner__username', 'session__title')


class EducatorTransactionInline(TabularInline):
    model = EducatorTransaction
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(EducatorWallet)
class EducatorWalletAdmin(ModelAdmin):
    list_display = ('educator', 'balance', 'total_earned', 'total_withdrawn', 'updated_at')
    search_fields = ('educator__username',)
    readonly_fields = ('total_earned', 'total_withdrawn', 'updated_at')
    inlines = [EducatorTransactionInline]


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(ModelAdmin):
    list_display = ('get_educator', 'amount', 'bank_name', 'account_number', 'account_name', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('wallet__educator__username', 'account_name', 'bank_name')
    readonly_fields = ('created_at',)
    fields = ('wallet', 'amount', 'bank_name', 'account_number', 'account_name', 'status', 'admin_note', 'created_at')

    def get_educator(self, obj):
        return obj.wallet.educator.username
    get_educator.short_description = 'Educator'

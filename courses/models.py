import uuid
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Course(models.Model):
    SKILL_LEVEL = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('all_levels', 'All Levels'),
    )

    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_taught')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses')
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    thumbnail = models.ImageField(upload_to='courses/thumbnails/', blank=True, null=True)
    skill_level = models.CharField(max_length=20, choices=SKILL_LEVEL, default='beginner')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_free = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    # Duration info
    duration_weeks = models.PositiveIntegerField(default=1)
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    hours_per_week = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    is_self_paced = models.BooleanField(default=True)

    # Info / meta
    tools_used = models.CharField(max_length=500, blank=True, default='')
    ideal_for = models.TextField(blank=True, default='')
    what_included = models.TextField(blank=True, default='')
    what_you_learn = models.TextField(blank=True, default='')
    certificate_url = models.URLField(blank=True, default='')

    # Reward tokens awarded on full course completion
    completion_tokens = models.PositiveIntegerField(default=50)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            from django.utils.text import slugify
            import uuid
            base = slugify(self.title)[:50] or 'course'
            slug = base
            qs = Course.objects.exclude(pk=self.pk) if self.pk else Course.objects
            if qs.filter(slug=slug).exists():
                slug = f'{base}-{uuid.uuid4().hex[:6]}'
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if not reviews:
            return 0
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def total_reviews(self):
        return self.reviews.count()

    @property
    def total_enrolled(self):
        return self.enrollments.count()


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    # Tokens awarded when learner completes this module
    reward_tokens = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.course.title} — Module {self.order}: {self.title}'


class Lesson(models.Model):
    LESSON_TYPE = (
        ('video', 'Video'),
        ('reading', 'Reading'),
        ('quiz', 'Quiz'),
        ('assignment', 'Assignment'),
    )

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE, default='video')
    order = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(default=0)
    video_file = models.FileField(upload_to='courses/videos/', blank=True, null=True)
    content = models.TextField(blank=True, default='')
    transcript = models.TextField(blank=True, default='')
    is_free_preview = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.module.title} — {self.title}'


class Quiz(models.Model):
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz', null=True, blank=True)
    module = models.OneToOneField(Module, on_delete=models.CASCADE, related_name='quiz', null=True, blank=True)
    title = models.CharField(max_length=255)
    pass_score = models.PositiveIntegerField(default=70, help_text='Minimum % to pass')
    reward_tokens = models.PositiveIntegerField(default=5)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text[:80]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


class Assessment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assessments')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='assessments', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    assessment_type = models.CharField(
        max_length=20,
        choices=(('graded', 'Graded'), ('practice', 'Practice')),
        default='graded',
    )
    duration_minutes = models.PositiveIntegerField(default=20)
    due_date = models.DateField(null=True, blank=True)
    reward_tokens = models.PositiveIntegerField(default=15)

    def __str__(self):
        return self.title


class CourseResource(models.Model):
    RESOURCE_TYPE = (
        ('article', 'Article'),
        ('pdf', 'PDF'),
        ('podcast', 'Podcast'),
        ('demo', 'Interactive Demo'),
        ('tool', 'Tool / Template'),
        ('event', 'Upcoming Event'),
        ('glossary', 'Glossary'),
        ('video', 'Video'),
        ('faq', 'FAQ'),
    )

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='resources')
    title = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE)
    url = models.URLField(blank=True, default='')
    file = models.FileField(upload_to='courses/resources/', blank=True, null=True)
    description = models.TextField(blank=True, default='')

    def __str__(self):
        return f'{self.course.title} — {self.title}'


class Enrollment(models.Model):
    learner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percent = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('learner', 'course')

    def __str__(self):
        return f'{self.learner.username} → {self.course.title}'


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progress')
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('enrollment', 'lesson')


class ModuleProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='module_progress')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='progress')
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_claimed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('enrollment', 'module')


class Review(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    learner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('course', 'learner')

    def __str__(self):
        return f'{self.learner.username} — {self.course.title} ({self.rating}★)'


class TokenWallet(models.Model):
    learner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.learner.username} — {self.balance} tokens'


class TokenTransaction(models.Model):
    REASON = (
        ('module_complete', 'Module Completed'),
        ('course_complete', 'Course Completed'),
        ('quiz_pass', 'Quiz Passed'),
        ('assessment_pass', 'Assessment Passed'),
        ('community', 'Community Contribution'),
        ('streak', 'Learning Streak'),
    )

    wallet = models.ForeignKey(TokenWallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.PositiveIntegerField()
    reason = models.CharField(max_length=30, choices=REASON)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_claimed = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.wallet.learner.username} +{self.amount} ({self.reason})'


class Certificate(models.Model):
    CERT_TYPE = (
        ('standard', 'Standard'),
        ('nft', 'NFT'),
    )

    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='certificate')
    certificate_id = models.CharField(max_length=20, unique=True, blank=True)
    cert_type = models.CharField(max_length=10, choices=CERT_TYPE)
    issued_at = models.DateTimeField(auto_now_add=True)
    # Standard cert — PDF generated/uploaded here
    pdf_file = models.FileField(upload_to='certificates/', blank=True, null=True)
    # QR code for verification
    qr_code = models.ImageField(upload_to='certificates/qr/', blank=True, null=True)
    # NFT cert — blockchain tx hash stored here once integration is live
    nft_tx_hash = models.CharField(max_length=255, blank=True, default='')

    def save(self, *args, **kwargs):
        if not self.certificate_id:
            # Generate alphanumeric certificate ID: ED3-XXXX-XXXX
            while True:
                unique_id = uuid.uuid4().hex[:8].upper()
                certificate_id = f'ED3-{unique_id[:4]}-{unique_id[4:8]}'
                # Ensure uniqueness
                if not Certificate.objects.filter(certificate_id=certificate_id).exists():
                    self.certificate_id = certificate_id
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.certificate_id} — {self.enrollment.learner.username} — {self.enrollment.course.title}'


class Session(models.Model):
    SESSION_TYPE = (
        ('live_qa', 'Live Q&A'),
        ('workshop', 'Workshop'),
        ('office_hours', 'Office Hours'),
        ('webinar', 'Webinar'),
    )
    
    STATUS = (
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    session_type = models.CharField(max_length=20, choices=SESSION_TYPE, default='live_qa')
    status = models.CharField(max_length=20, choices=STATUS, default='scheduled')
    
    # Date and time
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    
    # Meeting details
    meeting_link = models.URLField(blank=True, default='')
    meeting_platform = models.CharField(max_length=50, blank=True, default='')  # Zoom, Google Meet, etc.
    max_participants = models.PositiveIntegerField(default=0, help_text='0 = unlimited')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date', '-scheduled_time']

    def __str__(self):
        return f'{self.title} - {self.scheduled_date} at {self.scheduled_time}'


class SessionRegistration(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='registrations')
    learner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='session_registrations')
    registered_at = models.DateTimeField(auto_now_add=True)
    attended = models.BooleanField(default=False)

    class Meta:
        unique_together = ('session', 'learner')

    def __str__(self):
        return f'{self.learner.username} → {self.session.title}'

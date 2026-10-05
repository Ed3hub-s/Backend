import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from courses.models import Course


class LiveClassBundle(models.Model):
    educator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='live_class_bundles')
    title = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.CharField(max_length=3, default='NGN')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class LiveClass(models.Model):
    bundle = models.ForeignKey(LiveClassBundle, on_delete=models.PROTECT, null=True, blank=True, related_name='classes')
    LEVELS = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('all_levels', 'All Levels'),
    )
    ACCESS_TYPES = (('free', 'Free'), ('paid', 'Paid'))
    STATUSES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('live', 'Live'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    educator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='live_classes_taught',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='live_classes',
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField()
    category = models.CharField(max_length=100)
    level = models.CharField(max_length=20, choices=LEVELS)
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(validators=[MinValueValidator(15)])
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)])
    cover_image = models.ImageField(upload_to='live_classes/covers/', null=True, blank=True)
    learning_objectives = models.TextField()
    requirements = models.TextField(blank=True, default='')
    access_type = models.CharField(max_length=10, choices=ACCESS_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='NGN')
    status = models.CharField(max_length=12, choices=STATUSES, default='draft')
    recording_enabled = models.BooleanField(default=False)

    # Cloudflare RealtimeKit v1 meeting identity. API credentials never live here.
    cloudflare_meeting_id = models.CharField(max_length=64, blank=True, default='')
    cloudflare_host_participant_id = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('scheduled_date', 'scheduled_time')
        indexes = [
            models.Index(fields=('status', 'scheduled_date')),
            models.Index(fields=('category', 'level')),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.access_type == 'paid' and self.price <= 0:
            raise ValidationError({'price': 'Paid classes must have a price greater than zero.'})
        if self.access_type == 'free' and self.price != 0:
            raise ValidationError({'price': 'Free classes must have a zero price.'})
        if self.course_id and self.course.instructor_id != self.educator_id:
            raise ValidationError({'course': 'You can only connect your own course.'})

    def save(self, *args, **kwargs):
        self.currency = self.currency.upper()
        if self.access_type == 'free':
            self.price = 0
        if not self.slug:
            base = slugify(self.title)[:240] or 'live-class'
            candidate = base
            while LiveClass.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f'{base}-{uuid.uuid4().hex[:6]}'
            self.slug = candidate
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def starts_at(self):
        value = datetime.combine(self.scheduled_date, self.scheduled_time)
        return timezone.make_aware(value, timezone.get_current_timezone())

    @property
    def ends_at(self):
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    def is_joinable(self, at=None):
        at = at or timezone.now()
        return (
            self.status in ('published', 'live')
            and self.starts_at - timedelta(minutes=settings.LIVE_CLASS_JOIN_EARLY_MINUTES) <= at
            <= self.ends_at + timedelta(minutes=settings.LIVE_CLASS_JOIN_LATE_MINUTES)
        )


class LiveClassPayment(models.Model):
    STATUSES = (
        ('pending', 'Pending'),
        ('successful', 'Successful'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='live_class_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    transaction_reference = models.CharField(max_length=120, unique=True)
    payment_provider = models.CharField(max_length=30, default='paystack')
    status = models.CharField(max_length=12, choices=STATUSES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.transaction_reference} ({self.status})'


class LiveClassRegistration(models.Model):
    REGISTRATION_STATUSES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    )
    ACCESS_STATUSES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('revoked', 'Revoked'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    )

    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name='registrations')
    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='live_class_registrations',
    )
    payment = models.ForeignKey(
        LiveClassPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registrations',
    )
    registration_status = models.CharField(max_length=12, choices=REGISTRATION_STATUSES, default='pending')
    access_status = models.CharField(max_length=12, choices=ACCESS_STATUSES, default='pending')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cloudflare_participant_id = models.CharField(max_length=64, blank=True, default='')
    registered_at = models.DateTimeField(auto_now_add=True)
    access_granted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('live_class', 'learner'), name='unique_live_class_learner'),
        ]
        indexes = [models.Index(fields=('learner', 'access_status'))]

    def __str__(self):
        return f'{self.learner} -> {self.live_class}'


class LiveClassAttendance(models.Model):
    """One visit per join, so leave/rejoin duration is accounted for correctly."""

    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name='attendance_visits')
    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='live_class_attendance')
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    provider_session_id = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ('joined_at',)
        indexes = [models.Index(fields=('live_class', 'learner'))]

    def close(self, at=None):
        if self.left_at:
            return
        self.left_at = at or timezone.now()
        self.duration_seconds = max(0, int((self.left_at - self.joined_at).total_seconds()))
        self.save(update_fields=('left_at', 'duration_seconds'))


class LiveClassRecording(models.Model):
    STATUSES = (('processing', 'Processing'), ('available', 'Available'), ('failed', 'Failed'))

    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name='recordings')
    provider_recording_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=12, choices=STATUSES, default='processing')
    playback_url = models.URLField(max_length=2000, blank=True, default='')
    duration_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    available_at = models.DateTimeField(null=True, blank=True)


class LiveClassReminder(models.Model):
    TYPES = (('3_days', '3 days'), ('1_day', '1 day'), ('1_hour', '1 hour'), ('start', 'At start'))
    STATUSES = (('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'))

    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name='reminders')
    reminder_type = models.CharField(max_length=10, choices=TYPES)
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUSES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('live_class', 'reminder_type'), name='unique_live_class_reminder'),
        ]
        ordering = ('scheduled_for',)

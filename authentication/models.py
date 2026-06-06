import secrets

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .email_utils import build_branded_email_html, build_plain_email_from_html, send_smart_email


class UserProfile(models.Model):
    ROLE_CHOICES = (('learner', 'Learner'), ('educator', 'Educator'), ('marketer', 'Marketer'))
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='learner')
    bio = models.TextField(blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    city_country = models.CharField(max_length=100, blank=True, default='')
    specialization = models.CharField(max_length=255, blank=True, default='')
    experience = models.CharField(max_length=100, blank=True, default='')
    whatsapp = models.CharField(max_length=30, blank=True, default='')
    facebook = models.URLField(max_length=255, blank=True, default='')
    twitter_x = models.URLField(max_length=255, blank=True, default='')
    linkedin = models.URLField(max_length=255, blank=True, default='')
    instagram = models.URLField(max_length=255, blank=True, default='')

    def __str__(self):
        return f'{self.user.username} - {self.role}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.role == 'marketer':
            AffiliateMarketer.objects.get_or_create(user=self.user)
            MarketerWallet.objects.get_or_create(marketer=self.user)


class OTPCode(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        return timezone.now() < self.expires_at

    def __str__(self):
        return f'{self.email} - {self.code}'


class NewsletterContact(models.Model):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=80, blank=True, default='')
    last_name = models.CharField(max_length=80, blank=True, default='')
    source = models.CharField(max_length=120, blank=True, default='csv-import')
    is_subscribed = models.BooleanField(default=True)
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='newsletter_contacts_imported')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('email',)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class NewsletterCampaign(models.Model):
    AUDIENCE_ALL = 'all'
    AUDIENCE_LEARNERS = 'learners'
    AUDIENCE_EDUCATORS = 'educators'
    AUDIENCE_IMPORTED = 'imported'
    AUDIENCE_EVERYONE = 'everyone'
    AUDIENCE_CHOICES = (
        (AUDIENCE_ALL, 'Platform users'),
        (AUDIENCE_LEARNERS, 'Learners only'),
        (AUDIENCE_EDUCATORS, 'Educators only'),
        (AUDIENCE_IMPORTED, 'Imported contacts only'),
        (AUDIENCE_EVERYONE, 'Platform users and imported contacts'),
    )

    STATUS_DRAFT = 'draft'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_SENDING = 'sending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_SENDING, 'Sending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    )

    title = models.CharField(max_length=150, help_text='Internal name shown only in admin.')
    subject = models.CharField(max_length=180)
    preheader = models.CharField(
        max_length=180,
        blank=True,
        default='',
        help_text='Short preview text some inboxes show after the subject.',
    )
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    header_title = models.CharField(max_length=120, default='Ed3Hub Newsletter')
    header_subtitle = models.CharField(max_length=180, default='Updates for learners and educators')
    body_html = models.TextField(
        help_text='Main newsletter body. Simple HTML is allowed, for example <p>, <strong>, <ul>, and <a>.',
    )
    cta_text = models.CharField(max_length=80, blank=True, default='', verbose_name='Button text')
    cta_url = models.URLField(blank=True, default='', verbose_name='Button URL')
    footer_note = models.TextField(
        blank=True,
        default='You are receiving this email because you joined Ed3Hub as a learner or educator.',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    scheduled_for = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='newsletters_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    total_recipients = models.PositiveIntegerField(default=0)
    successful_sends = models.PositiveIntegerField(default=0)
    failed_sends = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default='')

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'

    def recipient_queryset(self):
        qs = User.objects.filter(is_active=True).exclude(email='').select_related('profile').order_by('id')
        if self.audience == self.AUDIENCE_LEARNERS:
            qs = qs.filter(profile__role='learner')
        elif self.audience == self.AUDIENCE_EDUCATORS:
            qs = qs.filter(profile__role='educator')
        return qs

    def imported_contact_queryset(self):
        if self.audience not in (self.AUDIENCE_IMPORTED, self.AUDIENCE_EVERYONE):
            return NewsletterContact.objects.none()
        return NewsletterContact.objects.filter(is_subscribed=True).exclude(email='').order_by('email')

    def recipient_emails(self):
        emails = []
        if self.audience != self.AUDIENCE_IMPORTED:
            emails.extend(self.recipient_queryset().values_list('email', flat=True))
        emails.extend(self.imported_contact_queryset().values_list('email', flat=True))

        seen = set()
        unique_emails = []
        for email in emails:
            normalized_email = (email or '').strip().lower()
            if normalized_email and normalized_email not in seen:
                seen.add(normalized_email)
                unique_emails.append(normalized_email)
        return unique_emails

    def render_html(self):
        return build_branded_email_html(
            subject=self.subject,
            body_html=self.body_html,
            preheader=self.preheader,
            header_title=self.header_title,
            header_subtitle=self.header_subtitle,
            footer_note=self.footer_note,
            cta_text=self.cta_text,
            cta_url=self.cta_url,
        )

    def render_plain_text(self):
        return build_plain_email_from_html(self.body_html, self.footer_note)

    def send(self, *, fail_silently=True):
        recipients = self.recipient_emails()
        self.status = self.STATUS_SENDING
        self.total_recipients = len(recipients)
        self.successful_sends = 0
        self.failed_sends = 0
        self.last_error = ''
        self.save(update_fields=[
            'status', 'total_recipients', 'successful_sends',
            'failed_sends', 'last_error', 'updated_at',
        ])

        html_message = self.render_html()
        plain_message = self.render_plain_text()

        for email in recipients:
            try:
                send_smart_email(
                    subject=self.subject,
                    body=plain_message,
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=False,
                )
                NewsletterDeliveryLog.objects.create(campaign=self, email=email, status=NewsletterDeliveryLog.STATUS_SENT)
                self.successful_sends += 1
            except Exception as exc:
                NewsletterDeliveryLog.objects.create(
                    campaign=self,
                    email=email,
                    status=NewsletterDeliveryLog.STATUS_FAILED,
                    error=str(exc),
                )
                self.failed_sends += 1
                self.last_error = str(exc)
                if not fail_silently:
                    self.status = self.STATUS_FAILED
                    self.save(update_fields=['status', 'successful_sends', 'failed_sends', 'last_error', 'updated_at'])
                    raise

        self.status = self.STATUS_SENT if self.failed_sends == 0 else self.STATUS_FAILED
        self.sent_at = timezone.now()
        self.save(update_fields=[
            'status', 'successful_sends', 'failed_sends',
            'last_error', 'sent_at', 'updated_at',
        ])
        return self.successful_sends, self.failed_sends


class NewsletterDeliveryLog(models.Model):
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = (
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    )

    campaign = models.ForeignKey(NewsletterCampaign, on_delete=models.CASCADE, related_name='delivery_logs')
    email = models.EmailField()
    status = models.CharField(max_length=8, choices=STATUS_CHOICES)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.email} - {self.status}'


class AffiliateMarketer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate_marketer')
    referral_code = models.CharField(max_length=16, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='affiliate_marketers_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_referral_code():
        while True:
            code = secrets.token_urlsafe(6).replace('-', '').replace('_', '').upper()[:10]
            if code and not AffiliateMarketer.objects.filter(referral_code=code).exists():
                return code

    @property
    def affiliate_link(self):
        frontend_url = getattr(settings, 'AFFILIATE_FRONTEND_URL', 'https://ed3hub.com').rstrip('/')
        return f'{frontend_url}/sign-up?ref={self.referral_code}'

    def __str__(self):
        return f'{self.user.username} - {self.referral_code}'


class MarketerWallet(models.Model):
    marketer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='marketer_wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.marketer.username} - ₦{self.balance}'


class AffiliateReferral(models.Model):
    marketer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='affiliate_referrals')
    referred_user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate_referral')
    referral_code = models.CharField(max_length=16)
    signup_bonus_paid = models.BooleanField(default=False)
    first_purchase_reward_paid = models.BooleanField(default=False)
    first_purchase_course = models.ForeignKey(
        'courses.Course',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='affiliate_first_purchase_referrals',
    )
    first_purchase_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    first_purchase_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    first_purchase_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.referred_user.username} via {self.marketer.username}'


class MarketerTransaction(models.Model):
    TYPE_CHOICES = (
        ('signup_bonus', 'Signup Bonus'),
        ('purchase_commission', 'Purchase Commission'),
        ('withdrawal', 'Withdrawal'),
    )

    wallet = models.ForeignKey(MarketerWallet, on_delete=models.CASCADE, related_name='transactions')
    referral = models.ForeignKey(AffiliateReferral, on_delete=models.SET_NULL, blank=True, null=True, related_name='transactions')
    referred_user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='marketer_transactions_from_signup')
    course = models.ForeignKey('courses.Course', on_delete=models.SET_NULL, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=24, choices=TYPE_CHOICES)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.wallet.marketer.username} {self.transaction_type} ₦{self.amount}'

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from .models import NewsletterCampaign, NewsletterDeliveryLog, UserProfile, OTPCode

admin.site.unregister(User)


class UserProfileInline(TabularInline):
    model = UserProfile
    extra = 0
    fields = ('role', 'bio', 'avatar')


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    inlines = [UserProfileInline]


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    list_display = ('user', 'role', 'bio')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(OTPCode)
class OTPCodeAdmin(ModelAdmin):
    list_display = ('email', 'code', 'created_at', 'expires_at')
    search_fields = ('email',)
    readonly_fields = ('created_at',)


class NewsletterDeliveryLogInline(TabularInline):
    model = NewsletterDeliveryLog
    extra = 0
    can_delete = False
    fields = ('email', 'status', 'error', 'created_at')
    readonly_fields = ('email', 'status', 'error', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(NewsletterCampaign)
class NewsletterCampaignAdmin(ModelAdmin):
    list_display = (
        'title', 'audience', 'status', 'scheduled_for',
        'total_recipients', 'successful_sends', 'failed_sends', 'created_at',
    )
    list_filter = ('audience', 'status', 'created_at', 'scheduled_for')
    search_fields = ('title', 'subject', 'body_html')
    readonly_fields = (
        'created_by', 'created_at', 'updated_at', 'sent_at',
        'total_recipients', 'successful_sends', 'failed_sends',
        'last_error', 'recipient_count', 'email_preview',
    )
    fieldsets = (
        ('Audience', {
            'fields': ('title', 'audience', 'recipient_count', 'status', 'scheduled_for'),
        }),
        ('Email Content', {
            'fields': (
                'subject', 'preheader', 'header_title', 'header_subtitle',
                'body_html', 'cta_text', 'cta_url', 'footer_note', 'email_preview',
            ),
        }),
        ('Send Report', {
            'fields': (
                'created_by', 'created_at', 'updated_at', 'sent_at',
                'total_recipients', 'successful_sends', 'failed_sends', 'last_error',
            ),
        }),
    )
    inlines = [NewsletterDeliveryLogInline]
    actions = ('send_newsletters_now', 'schedule_newsletters')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def recipient_count(self, obj):
        if not obj.pk:
            return 'Save first to calculate recipients.'
        return obj.recipient_queryset().count()
    recipient_count.short_description = 'Matching recipients'

    def email_preview(self, obj):
        if not obj.pk:
            return 'Save first to preview the branded email.'
        return format_html(
            '<iframe srcdoc="{}" style="width: 100%; min-height: 520px; border: 1px solid #e5e7eb; border-radius: 12px; background: white;"></iframe>',
            obj.render_html(),
        )
    email_preview.short_description = 'Preview'

    @admin.action(description='Send selected newsletters now')
    def send_newsletters_now(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, 'Only super admins can send newsletters.', messages.ERROR)
            return

        sent_total = 0
        failed_total = 0
        for campaign in queryset.exclude(status=NewsletterCampaign.STATUS_SENDING):
            sent, failed = campaign.send()
            sent_total += sent
            failed_total += failed

        self.message_user(
            request,
            f'Newsletter delivery finished. Sent: {sent_total}. Failed: {failed_total}.',
            messages.SUCCESS if failed_total == 0 else messages.WARNING,
        )

    @admin.action(description='Mark selected newsletters as scheduled')
    def schedule_newsletters(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, 'Only super admins can schedule newsletters.', messages.ERROR)
            return

        updated = queryset.filter(scheduled_for__isnull=False).update(status=NewsletterCampaign.STATUS_SCHEDULED)
        self.message_user(request, f'{updated} newsletter(s) marked as scheduled.', messages.SUCCESS)


@admin.register(NewsletterDeliveryLog)
class NewsletterDeliveryLogAdmin(ModelAdmin):
    list_display = ('campaign', 'email', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('campaign__title', 'email', 'error')
    readonly_fields = ('campaign', 'email', 'status', 'error', 'created_at')

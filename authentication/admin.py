from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .forms import NewsletterContactCSVImportForm
from .models import (
    AffiliateMarketer,
    AffiliateReferral,
    MarketerTransaction,
    MarketerWallet,
    NewsletterCampaign,
    NewsletterContact,
    NewsletterDeliveryLog,
    OTPCode,
    UserProfile,
)
from .newsletter_import import import_newsletter_contacts

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


class MarketerTransactionInline(TabularInline):
    model = MarketerTransaction
    extra = 0
    can_delete = False
    readonly_fields = ('referral', 'referred_user', 'course', 'amount', 'transaction_type', 'description', 'created_at')
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AffiliateMarketer)
class AffiliateMarketerAdmin(ModelAdmin):
    list_display = ('user', 'referral_code', 'is_active', 'affiliate_link_display', 'created_by', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__username', 'user__email', 'referral_code')
    readonly_fields = ('referral_code', 'affiliate_link_display', 'created_by', 'created_at')

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        if obj.scheduled_for and obj.status == NewsletterCampaign.STATUS_DRAFT:
            obj.status = NewsletterCampaign.STATUS_SCHEDULED
        super().save_model(request, obj, form, change)
        profile, _ = UserProfile.objects.get_or_create(user=obj.user)
        if profile.role != 'marketer':
            profile.role = 'marketer'
            profile.save(update_fields=['role'])

    def affiliate_link_display(self, obj):
        if not obj.pk:
            return 'Save first to generate link.'
        return obj.affiliate_link
    affiliate_link_display.short_description = 'Affiliate link'


@admin.register(MarketerWallet)
class MarketerWalletAdmin(ModelAdmin):
    list_display = ('marketer', 'balance', 'total_earned', 'total_withdrawn', 'updated_at')
    search_fields = ('marketer__username', 'marketer__email')
    readonly_fields = ('balance', 'total_earned', 'total_withdrawn', 'updated_at')
    inlines = [MarketerTransactionInline]


@admin.register(AffiliateReferral)
class AffiliateReferralAdmin(ModelAdmin):
    list_display = (
        'referred_user', 'marketer', 'signup_bonus_paid',
        'first_purchase_reward_paid', 'first_purchase_course',
        'first_purchase_commission', 'created_at',
    )
    list_filter = ('signup_bonus_paid', 'first_purchase_reward_paid', 'created_at')
    search_fields = ('marketer__username', 'referred_user__username', 'referred_user__email', 'referral_code')
    readonly_fields = (
        'marketer', 'referred_user', 'referral_code', 'signup_bonus_paid',
        'first_purchase_reward_paid', 'first_purchase_course',
        'first_purchase_amount', 'first_purchase_commission',
        'created_at', 'first_purchase_at',
    )


@admin.register(MarketerTransaction)
class MarketerTransactionAdmin(ModelAdmin):
    list_display = ('wallet', 'transaction_type', 'amount', 'referred_user', 'course', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('wallet__marketer__username', 'referred_user__username', 'course__title', 'description')
    readonly_fields = ('wallet', 'referral', 'referred_user', 'course', 'amount', 'transaction_type', 'description', 'created_at')


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


@admin.register(NewsletterContact)
class NewsletterContactAdmin(ModelAdmin):
    change_list_template = 'admin/authentication/newslettercontact/change_list.html'
    list_display = ('email', 'first_name', 'last_name', 'source', 'is_subscribed', 'created_at')
    list_filter = ('is_subscribed', 'source', 'created_at')
    search_fields = ('email', 'first_name', 'last_name', 'source')
    readonly_fields = ('created_at', 'updated_at', 'imported_by')
    actions = ('mark_subscribed', 'mark_unsubscribed')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'import-csv/',
                self.admin_site.admin_view(self.import_csv_view),
                name='authentication_newslettercontact_import_csv',
            ),
        ]
        return custom_urls + urls

    def import_csv_view(self, request):
        if request.method == 'POST':
            form = NewsletterContactCSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                uploaded_file = form.cleaned_data['csv_file']
                decoded_file = uploaded_file.read().decode('utf-8-sig').splitlines()
                result = import_newsletter_contacts(
                    decoded_file,
                    source=form.cleaned_data.get('source') or 'csv-import',
                    imported_by=request.user,
                    update_existing=form.cleaned_data['update_existing'],
                )
                if result.errors:
                    messages.warning(
                        request,
                        f'Import completed with warnings. Created: {result.created}. Updated: {result.updated}. '
                        f'Skipped: {result.skipped}. First issue: {result.errors[0]}',
                    )
                else:
                    messages.success(
                        request,
                        f'Import completed. Created: {result.created}. Updated: {result.updated}. Skipped: {result.skipped}.',
                    )
                return redirect(reverse('admin:authentication_newslettercontact_changelist'))
        else:
            form = NewsletterContactCSVImportForm()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Import newsletter contacts',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/authentication/newslettercontact/import_csv.html', context)

    @admin.action(description='Mark selected contacts as subscribed')
    def mark_subscribed(self, request, queryset):
        updated = queryset.update(is_subscribed=True)
        self.message_user(request, f'{updated} contact(s) marked as subscribed.', messages.SUCCESS)

    @admin.action(description='Mark selected contacts as unsubscribed')
    def mark_unsubscribed(self, request, queryset):
        updated = queryset.update(is_subscribed=False)
        self.message_user(request, f'{updated} contact(s) marked as unsubscribed.', messages.SUCCESS)


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
        return len(obj.recipient_emails())
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

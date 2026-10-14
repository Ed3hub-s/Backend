from django.contrib import admin
from django.db.models import Count, Q, Sum

from .models import (
    LiveClass,
    LiveClassBundle,
    LiveClassAttendance,
    LiveClassPayment,
    LiveClassRecording,
    LiveClassRegistration,
    LiveClassReminder,
)


class LiveClassRegistrationInline(admin.TabularInline):
    model = LiveClassRegistration
    extra = 0
    fields = ('learner', 'learner_email', 'registration_status', 'access_status', 'amount_paid', 'payment', 'registered_at')
    readonly_fields = fields

    @admin.display(description='Email')
    def learner_email(self, obj):
        return obj.learner.email

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LiveClass)
class LiveClassAdmin(admin.ModelAdmin):
    list_display = ('title', 'educator', 'confirmed_learners', 'learner_names', 'paid_revenue', 'scheduled_date', 'scheduled_time', 'access_type', 'status')
    list_filter = ('status', 'access_type', 'level', 'category')
    search_fields = ('title', 'educator__username', 'educator__email')
    readonly_fields = ('cloudflare_meeting_id', 'cloudflare_host_participant_id', 'created_at', 'updated_at')
    inlines = (LiveClassRegistrationInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            confirmed_learner_count=Count(
                'registrations',
                filter=Q(registrations__registration_status='confirmed', registrations__access_status='active'),
                distinct=True,
            ),
            collected_revenue=Sum(
                'registrations__amount_paid',
                filter=Q(registrations__registration_status='confirmed', registrations__access_status='active'),
            ),
        )

    @admin.display(description='Learners', ordering='confirmed_learner_count')
    def confirmed_learners(self, obj):
        return obj.confirmed_learner_count

    @admin.display(description='Learner names')
    def learner_names(self, obj):
        registrations = obj.registrations.filter(
            registration_status='confirmed', access_status='active',
        ).select_related('learner')[:5]
        names = [item.learner.get_full_name().strip() or item.learner.username for item in registrations]
        return ', '.join(names) if names else '-'

    @admin.display(description='Revenue', ordering='collected_revenue')
    def paid_revenue(self, obj):
        return f'{obj.currency} {obj.collected_revenue or 0}'


@admin.register(LiveClassRegistration)
class LiveClassRegistrationAdmin(admin.ModelAdmin):
    list_display = ('live_class', 'learner', 'learner_email', 'registration_status', 'access_status', 'amount_paid', 'payment', 'registered_at')
    list_filter = ('registration_status', 'access_status')
    search_fields = ('live_class__title', 'learner__username', 'learner__email')

    @admin.display(description='Email')
    def learner_email(self, obj):
        return obj.learner.email


@admin.register(LiveClassPayment)
class LiveClassPaymentAdmin(admin.ModelAdmin):
    readonly_fields = tuple(field.name for field in LiveClassPayment._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
    list_display = ('transaction_reference', 'user', 'user_email', 'class_names', 'amount', 'currency', 'status', 'educator_share', 'paid_at')
    list_filter = ('status', 'payment_provider')
    search_fields = ('transaction_reference', 'user__email')

    @admin.display(description='Email')
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description='Live classes')
    def class_names(self, obj):
        return ', '.join(obj.registrations.values_list('live_class__title', flat=True)) or '-'


admin.site.register(LiveClassAttendance)
admin.site.register(LiveClassRecording)
admin.site.register(LiveClassReminder)


@admin.register(LiveClassBundle)
class LiveClassBundleAdmin(admin.ModelAdmin):
    list_display = ('title', 'educator', 'price', 'currency')
    readonly_fields = tuple(field.name for field in LiveClassBundle._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

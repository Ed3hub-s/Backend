from django.contrib import admin

from .models import (
    LiveClass,
    LiveClassAttendance,
    LiveClassPayment,
    LiveClassRecording,
    LiveClassRegistration,
    LiveClassReminder,
)


@admin.register(LiveClass)
class LiveClassAdmin(admin.ModelAdmin):
    list_display = ('title', 'educator', 'scheduled_date', 'scheduled_time', 'access_type', 'status')
    list_filter = ('status', 'access_type', 'level', 'category')
    search_fields = ('title', 'educator__username', 'educator__email')
    readonly_fields = ('cloudflare_meeting_id', 'cloudflare_host_participant_id', 'created_at', 'updated_at')


@admin.register(LiveClassRegistration)
class LiveClassRegistrationAdmin(admin.ModelAdmin):
    list_display = ('live_class', 'learner', 'registration_status', 'access_status', 'registered_at')
    list_filter = ('registration_status', 'access_status')
    search_fields = ('live_class__title', 'learner__username', 'learner__email')


@admin.register(LiveClassPayment)
class LiveClassPaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_reference', 'user', 'amount', 'currency', 'status', 'paid_at')
    list_filter = ('status', 'payment_provider')
    search_fields = ('transaction_reference', 'user__email')


admin.site.register(LiveClassAttendance)
admin.site.register(LiveClassRecording)
admin.site.register(LiveClassReminder)

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from unfold.admin import ModelAdmin, TabularInline
from .models import UserProfile, OTPCode

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

from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=['learner', 'educator'], default='learner')

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'role')

    def create(self, validated_data):
        role = validated_data.pop('role', 'learner')
        user = User.objects.create_user(**validated_data)
        UserProfile.objects.create(user=user, role=role)
        return user


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    bio = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    city_country = serializers.SerializerMethodField()
    specialization = serializers.SerializerMethodField()
    experience = serializers.SerializerMethodField()
    whatsapp = serializers.SerializerMethodField()
    facebook = serializers.SerializerMethodField()
    twitter_x = serializers.SerializerMethodField()
    linkedin = serializers.SerializerMethodField()
    instagram = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'role', 'bio', 'avatar',
                  'city_country', 'specialization', 'experience',
                  'whatsapp', 'facebook', 'twitter_x', 'linkedin', 'instagram')

    def _profile(self, obj):
        try:
            return obj.profile
        except UserProfile.DoesNotExist:
            return None

    def get_role(self, obj):
        p = self._profile(obj)
        return p.role if p else 'learner'

    def get_bio(self, obj):
        p = self._profile(obj)
        return p.bio if p else ''

    def get_avatar(self, obj):
        p = self._profile(obj)
        if p and p.avatar:
            request = self.context.get('request')
            return request.build_absolute_uri(p.avatar.url) if request else p.avatar.url
        return None

    def get_city_country(self, obj):
        p = self._profile(obj); return p.city_country if p else ''

    def get_specialization(self, obj):
        p = self._profile(obj); return p.specialization if p else ''

    def get_experience(self, obj):
        p = self._profile(obj); return p.experience if p else ''

    def get_whatsapp(self, obj):
        p = self._profile(obj); return p.whatsapp if p else ''

    def get_facebook(self, obj):
        p = self._profile(obj); return p.facebook if p else ''

    def get_twitter_x(self, obj):
        p = self._profile(obj); return p.twitter_x if p else ''

    def get_linkedin(self, obj):
        p = self._profile(obj); return p.linkedin if p else ''

    def get_instagram(self, obj):
        p = self._profile(obj); return p.instagram if p else ''


class EducatorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    bio = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    total_courses = serializers.SerializerMethodField()
    city_country = serializers.SerializerMethodField()
    specialization = serializers.SerializerMethodField()
    experience = serializers.SerializerMethodField()
    whatsapp = serializers.SerializerMethodField()
    facebook = serializers.SerializerMethodField()
    twitter_x = serializers.SerializerMethodField()
    linkedin = serializers.SerializerMethodField()
    instagram = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'full_name', 'email', 'bio', 'avatar', 'total_courses',
                  'city_country', 'specialization', 'experience',
                  'whatsapp', 'facebook', 'twitter_x', 'linkedin', 'instagram')

    def _profile(self, obj):
        try:
            return obj.profile
        except UserProfile.DoesNotExist:
            return None

    def get_full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip() or obj.username

    def get_bio(self, obj):
        p = self._profile(obj); return p.bio if p else ''

    def get_avatar(self, obj):
        p = self._profile(obj)
        if p and p.avatar:
            request = self.context.get('request')
            return request.build_absolute_uri(p.avatar.url) if request else p.avatar.url
        return None

    def get_total_courses(self, obj):
        return obj.courses_taught.filter(is_published=True).count()

    def get_city_country(self, obj):
        p = self._profile(obj); return p.city_country if p else ''

    def get_specialization(self, obj):
        p = self._profile(obj); return p.specialization if p else ''

    def get_experience(self, obj):
        p = self._profile(obj); return p.experience if p else ''

    def get_whatsapp(self, obj):
        p = self._profile(obj); return p.whatsapp if p else ''

    def get_facebook(self, obj):
        p = self._profile(obj); return p.facebook if p else ''

    def get_twitter_x(self, obj):
        p = self._profile(obj); return p.twitter_x if p else ''

    def get_linkedin(self, obj):
        p = self._profile(obj); return p.linkedin if p else ''

    def get_instagram(self, obj):
        p = self._profile(obj); return p.instagram if p else ''


class GoogleAuthSerializer(serializers.Serializer):
    access_token = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class ResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

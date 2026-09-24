from django.utils import timezone
from rest_framework import serializers

from courses.models import Course

from .models import (
    LiveClass,
    LiveClassAttendance,
    LiveClassRecording,
    LiveClassRegistration,
)


class EducatorSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.get_full_name().strip() or obj.username

    def get_avatar(self, obj):
        profile = getattr(obj, 'profile', None)
        if not profile or not profile.avatar:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(profile.avatar.url) if request else profile.avatar.url


class LiveClassListSerializer(serializers.ModelSerializer):
    educator = EducatorSummarySerializer(read_only=True)
    registered_count = serializers.IntegerField(read_only=True)
    available_spaces = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    starts_at = serializers.DateTimeField(read_only=True)
    is_joinable = serializers.SerializerMethodField()
    viewer_access_status = serializers.SerializerMethodField()

    class Meta:
        model = LiveClass
        fields = (
            'id', 'slug', 'title', 'description', 'educator', 'category', 'level',
            'scheduled_date', 'scheduled_time', 'starts_at', 'duration_minutes',
            'capacity', 'registered_count', 'available_spaces', 'cover_image_url',
            'access_type', 'price', 'currency', 'status', 'recording_enabled',
            'is_joinable', 'viewer_access_status',
        )

    def get_available_spaces(self, obj):
        return max(0, obj.capacity - getattr(obj, 'registered_count', obj.registrations.filter(access_status='active').count()))

    def get_cover_image_url(self, obj):
        if not obj.cover_image:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.cover_image.url) if request else obj.cover_image.url

    def get_is_joinable(self, obj):
        return obj.is_joinable()

    def get_viewer_access_status(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        if obj.educator_id == request.user.id:
            return 'host'
        registration = next(
            (item for item in getattr(obj, 'viewer_registrations', []) if item.learner_id == request.user.id),
            None,
        )
        if registration is None:
            registration = obj.registrations.filter(learner=request.user).only('access_status').first()
        return registration.access_status if registration else None


class LiveClassDetailSerializer(LiveClassListSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    recordings_available = serializers.SerializerMethodField()

    class Meta(LiveClassListSerializer.Meta):
        fields = LiveClassListSerializer.Meta.fields + (
            'learning_objectives', 'requirements', 'course', 'course_title',
            'recordings_available', 'created_at', 'updated_at',
        )

    def get_recordings_available(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        authorized = obj.educator_id == request.user.id or obj.registrations.filter(
            learner=request.user, access_status='active'
        ).exists()
        return authorized and obj.recordings.filter(status='available').exists()


class LiveClassWriteSerializer(serializers.ModelSerializer):
    start_now = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = LiveClass
        fields = (
            'id', 'slug', 'course', 'title', 'description', 'category', 'level',
            'scheduled_date', 'scheduled_time', 'duration_minutes', 'capacity',
            'cover_image', 'learning_objectives', 'requirements', 'access_type',
            'price', 'currency', 'status', 'recording_enabled', 'start_now',
        )
        read_only_fields = ('id', 'slug')
        extra_kwargs = {
            'scheduled_date': {'required': False},
            'scheduled_time': {'required': False},
        }

    def validate_course(self, course):
        request = self.context['request']
        if course and course.instructor_id != request.user.id:
            raise serializers.ValidationError('You can only connect a course you teach.')
        return course

    def validate(self, attrs):
        start_now = attrs.get('start_now', False)
        if start_now:
            now = timezone.localtime().replace(second=0, microsecond=0)
            attrs['scheduled_date'] = now.date()
            attrs['scheduled_time'] = now.time()
        access_type = attrs.get('access_type', getattr(self.instance, 'access_type', None))
        price = attrs.get('price', getattr(self.instance, 'price', 0))
        if access_type == 'paid' and price <= 0:
            raise serializers.ValidationError({'price': 'Enter a price for a paid class.'})
        if access_type == 'free':
            attrs['price'] = 0
        date = attrs.get('scheduled_date', getattr(self.instance, 'scheduled_date', None))
        start_time = attrs.get('scheduled_time', getattr(self.instance, 'scheduled_time', None))
        if not self.instance and not start_now and (not date or not start_time):
            raise serializers.ValidationError({'scheduled_date': 'Choose a date and time or start the class now.'})
        if date and start_time:
            from datetime import datetime
            starts_at = timezone.make_aware(datetime.combine(date, start_time), timezone.get_current_timezone())
            schedule_changed = 'scheduled_date' in attrs or 'scheduled_time' in attrs
            if not start_now and (not self.instance or schedule_changed) and starts_at <= timezone.now():
                raise serializers.ValidationError({'scheduled_date': 'Live classes must be scheduled in the future.'})
        if not self.instance and not attrs.get('cover_image'):
            raise serializers.ValidationError({'cover_image': 'A cover image is required.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('start_now', None)
        return LiveClass.objects.create(educator=self.context['request'].user, **validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('start_now', None)
        return super().update(instance, validated_data)


class LiveClassRegistrationSerializer(serializers.ModelSerializer):
    live_class_title = serializers.CharField(source='live_class.title', read_only=True)
    live_class_slug = serializers.CharField(source='live_class.slug', read_only=True)
    starts_at = serializers.DateTimeField(source='live_class.starts_at', read_only=True)
    educator_name = serializers.SerializerMethodField()

    class Meta:
        model = LiveClassRegistration
        fields = (
            'id', 'live_class', 'live_class_title', 'live_class_slug', 'starts_at',
            'educator_name', 'registration_status', 'access_status', 'amount_paid',
            'registered_at', 'access_granted_at',
        )

    def get_educator_name(self, obj):
        return obj.live_class.educator.get_full_name().strip() or obj.live_class.educator.username


class AttendanceSerializer(serializers.ModelSerializer):
    learner_name = serializers.SerializerMethodField()

    class Meta:
        model = LiveClassAttendance
        fields = ('id', 'learner', 'learner_name', 'joined_at', 'left_at', 'duration_seconds')

    def get_learner_name(self, obj):
        return obj.learner.get_full_name().strip() or obj.learner.username


class RecordingSerializer(serializers.ModelSerializer):
    access_url = serializers.SerializerMethodField()

    class Meta:
        model = LiveClassRecording
        fields = ('id', 'status', 'duration_seconds', 'created_at', 'available_at', 'access_url')

    def get_access_url(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return request.build_absolute_uri(f'/api/live-classes/recordings/{obj.pk}/access/')


class CourseChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ('id', 'title')

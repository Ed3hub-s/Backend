from rest_framework import serializers

from courses.models import Course

from .models import AnalyticsEvent


class AnalyticsTrackSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(
        choices=(
            AnalyticsEvent.LANDING_PAGE_VIEW,
            AnalyticsEvent.COURSE_PAGE_VIEW,
            AnalyticsEvent.SEARCH_USED,
        )
    )
    course_id = serializers.IntegerField(required=False)
    metadata = serializers.JSONField(required=False)

    def validate_course_id(self, value):
        if not Course.objects.filter(id=value).exists():
            raise serializers.ValidationError('Course not found.')
        return value

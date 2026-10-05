from django.db import transaction
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import LiveClass, LiveClassBundle
from .permissions import IsEducator
from .serializers import LiveClassListSerializer


class BundleSerializer(serializers.ModelSerializer):
    classes = LiveClassListSerializer(many=True, read_only=True)
    class_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), write_only=True, min_length=2)

    class Meta:
        model = LiveClassBundle
        fields = ('id', 'title', 'description', 'price', 'currency', 'classes', 'class_ids')

    def validate_currency(self, value):
        return value.upper()

    @transaction.atomic
    def create(self, validated_data):
        class_ids = validated_data.pop('class_ids')
        if len(set(class_ids)) != len(class_ids):
            raise serializers.ValidationError('Choose at least two different classes.')
        educator = self.context['request'].user
        classes = list(LiveClass.objects.select_for_update().filter(pk__in=class_ids).order_by('pk'))
        if len(classes) != len(class_ids):
            raise serializers.ValidationError('One or more classes were not found.')
        currency = validated_data.get('currency', 'NGN')
        for item in classes:
            if item.educator_id != educator.pk or item.bundle_id or item.registrations.exists():
                raise serializers.ValidationError('Only your unbundled classes without registrations can be bundled.')
            if item.access_type != 'paid' or item.currency != currency:
                raise serializers.ValidationError('Select paid classes using the same currency as the bundle.')
            if item.status != 'published' or item.starts_at <= timezone.now():
                raise serializers.ValidationError('Bundle classes must be published and scheduled in the future.')
        bundle = LiveClassBundle.objects.create(educator=educator, **validated_data)
        LiveClass.objects.filter(pk__in=class_ids).update(bundle=bundle)
        return bundle


class BundleListView(generics.ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = BundleSerializer

    def get_queryset(self):
        return LiveClassBundle.objects.filter(classes__status__in=('published', 'live')).distinct().prefetch_related('classes__educator', 'classes__registrations')


class EducatorBundleView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, IsEducator)
    serializer_class = BundleSerializer

    def get_queryset(self):
        return LiveClassBundle.objects.filter(educator=self.request.user).prefetch_related('classes__educator', 'classes__registrations')

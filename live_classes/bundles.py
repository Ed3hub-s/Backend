import json
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LiveClass, LiveClassBundle
from .notifications import schedule_live_class_reminders
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


class EducatorProgramCreateView(APIView):
    """Create one paid programme and all of its live sessions atomically."""

    permission_classes = (IsAuthenticated, IsEducator)
    parser_classes = (FormParser, MultiPartParser)

    @transaction.atomic
    def post(self, request):
        try:
            sessions = json.loads(request.data.get('sessions', '[]'))
        except (TypeError, ValueError):
            return Response({'sessions': 'Sessions must be valid JSON.'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(sessions, list) or len(sessions) < 2:
            return Response({'sessions': 'Add at least two sessions to a multi-class programme.'}, status=status.HTTP_400_BAD_REQUEST)

        required = ('title', 'description', 'category', 'level', 'learning_objectives', 'price', 'currency', 'capacity')
        missing = [field for field in required if not str(request.data.get(field, '')).strip()]
        if missing:
            return Response({missing[0]: 'This field is required.'}, status=status.HTTP_400_BAD_REQUEST)
        cover = request.FILES.get('cover_image')
        if not cover:
            return Response({'cover_image': 'A programme cover image is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from decimal import Decimal
            price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01')).run_validation(request.data['price'])
            capacity = serializers.IntegerField(min_value=1, max_value=100).run_validation(request.data['capacity'])
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        course = None
        if request.data.get('course'):
            from courses.models import Course
            try:
                course = Course.objects.get(pk=request.data['course'], instructor=request.user)
            except Course.DoesNotExist:
                return Response({'course': 'You can only connect a course you teach.'}, status=status.HTTP_400_BAD_REQUEST)

        parsed_sessions = []
        for index, item in enumerate(sessions):
            if not isinstance(item, dict):
                return Response({'sessions': f'Session {index + 1} is invalid.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                title = str(item.get('title', '')).strip()
                if not title:
                    raise ValueError('Enter a session title.')
                starts_at = timezone.make_aware(
                    datetime.fromisoformat(f"{item.get('scheduled_date', '')}T{item.get('scheduled_time', '')}"),
                    timezone.get_current_timezone(),
                )
                duration = int(item.get('duration_minutes', 60))
                if duration < 15:
                    raise ValueError('Duration must be at least 15 minutes.')
                if starts_at <= timezone.now():
                    raise ValueError('Choose a future date and time.')
            except (TypeError, ValueError) as exc:
                return Response({'sessions': f'Session {index + 1}: {exc}'}, status=status.HTTP_400_BAD_REQUEST)
            parsed_sessions.append((title, starts_at, duration))

        bundle = LiveClassBundle.objects.create(
            educator=request.user,
            title=request.data['title'].strip(),
            description=request.data['description'].strip(),
            price=price,
            currency=request.data['currency'].upper(),
        )
        created = []
        shared_cover_name = None
        for index, (session_title, starts_at, duration) in enumerate(parsed_sessions):
            live_class = LiveClass.objects.create(
                bundle=bundle,
                educator=request.user,
                course=course,
                title=session_title,
                description=request.data['description'].strip(),
                category=request.data['category'],
                level=request.data['level'],
                scheduled_date=starts_at.date(),
                scheduled_time=starts_at.time(),
                duration_minutes=duration,
                capacity=capacity,
                cover_image=cover if index == 0 else shared_cover_name,
                learning_objectives=request.data['learning_objectives'].strip(),
                requirements=request.data.get('requirements', '').strip(),
                access_type='paid',
                price=price,
                currency=bundle.currency,
                status='published',
                recording_enabled=str(request.data.get('recording_enabled', '')).lower() == 'true',
            )
            if index == 0:
                shared_cover_name = live_class.cover_image.name
            schedule_live_class_reminders(live_class)
            created.append(live_class)

        return Response(BundleSerializer(bundle, context={'request': request}).data, status=status.HTTP_201_CREATED)

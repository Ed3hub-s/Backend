from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import LiveClass, LiveClassAttendance, LiveClassPayment, LiveClassRecording, LiveClassRegistration
from .notifications import schedule_live_class_reminders
from .permissions import IsEducator
from .serializers import (
    AttendanceSerializer,
    LiveClassDetailSerializer,
    LiveClassListSerializer,
    LiveClassRegistrationSerializer,
    LiveClassWriteSerializer,
    RecordingSerializer,
)
from .services import (
    CloudflareRealtimeKitV1,
    authorize_classroom,
    register_for_live_class,
    verify_live_class_payment,
)
from notifications.utils import NotificationService


def live_class_queryset(request=None):
    queryset = LiveClass.objects.select_related('educator', 'educator__profile', 'course').annotate(
        registered_count=Count('registrations', filter=Q(registrations__access_status='active'))
    )
    if request and request.user.is_authenticated:
        queryset = queryset.prefetch_related(
            Prefetch(
                'registrations',
                queryset=LiveClassRegistration.objects.filter(learner=request.user),
                to_attr='viewer_registrations',
            )
        )
    return queryset


class LiveClassMarketplaceView(generics.ListAPIView):
    serializer_class = LiveClassListSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        queryset = live_class_queryset(self.request).filter(
            status__in=('published', 'live'), scheduled_date__gte=timezone.localdate()
        )
        params = self.request.query_params
        if params.get('search'):
            term = params['search'].strip()
            queryset = queryset.filter(Q(title__icontains=term) | Q(description__icontains=term) | Q(category__icontains=term))
        for field in ('category', 'level', 'access_type'):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        if params.get('date'):
            queryset = queryset.filter(scheduled_date=params['date'])
        ordering = params.get('ordering')
        if ordering == 'popular':
            return queryset.order_by('-registered_count', 'scheduled_date', 'scheduled_time')
        return queryset.order_by('scheduled_date', 'scheduled_time')


class LiveClassDetailView(generics.RetrieveAPIView):
    serializer_class = LiveClassDetailSerializer
    permission_classes = (AllowAny,)
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = live_class_queryset(self.request)
        if not self.request.user.is_authenticated:
            return queryset.filter(status__in=('published', 'live', 'completed'))
        return queryset.filter(
            Q(status__in=('published', 'live', 'completed')) | Q(educator=self.request.user)
        )


class EducatorLiveClassListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated, IsEducator)
    parser_classes = (JSONParser, FormParser, MultiPartParser)

    def get_queryset(self):
        return live_class_queryset(self.request).filter(educator=self.request.user)

    def get_serializer_class(self):
        return LiveClassWriteSerializer if self.request.method == 'POST' else LiveClassListSerializer

    def perform_create(self, serializer):
        live_class = serializer.save()
        schedule_live_class_reminders(live_class)


class EducatorLiveClassDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated, IsEducator)
    parser_classes = (JSONParser, FormParser, MultiPartParser)
    serializer_class = LiveClassWriteSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return LiveClass.objects.filter(educator=self.request.user)

    def perform_update(self, serializer):
        live_class = serializer.save()
        schedule_live_class_reminders(live_class)

    def perform_destroy(self, instance):
        if instance.registrations.exists():
            raise ValidationError('Classes with registrations cannot be deleted; cancel the class instead.')
        instance.delete()


class RegisterLiveClassView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, slug):
        live_class = get_object_or_404(LiveClass, slug=slug)
        registration, checkout, created = register_for_live_class(live_class, request.user)
        if created:
            NotificationService.create_notification(
                recipient=live_class.educator,
                notification_type='live_class_registered',
                title='New live class registration',
                message=f'{request.user.get_full_name().strip() or request.user.username} registered for {live_class.title}',
                live_class=live_class,
                action_url=f'/live-classes/manage/{live_class.slug}',
            )
        payload = {
            'registration': LiveClassRegistrationSerializer(registration).data,
            'checkout': checkout,
        }
        return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class VerifyLiveClassPaymentView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, slug):
        reference = request.data.get('reference', '').strip()
        if not reference:
            raise ValidationError({'reference': 'Payment reference is required.'})
        registration = get_object_or_404(
            LiveClassRegistration.objects.select_related('payment', 'live_class'),
            live_class__slug=slug,
            learner=request.user,
        )
        registration = verify_live_class_payment(registration, reference)
        return Response(LiveClassRegistrationSerializer(registration).data)


class PaystackLiveClassWebhookView(APIView):
    """Reconcile paid access even when the learner closes the checkout callback."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request):
        signature = request.headers.get('x-paystack-signature', '')
        expected = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            request.body,
            hashlib.sha512,
        ).hexdigest()
        if not settings.PAYSTACK_SECRET_KEY or not hmac.compare_digest(signature, expected):
            return Response({'detail': 'Invalid signature.'}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            event = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({'detail': 'Invalid payload.'}, status=status.HTTP_400_BAD_REQUEST)

        event_name = event.get('event')
        event_data = event.get('data') or {}
        transaction_data = event_data.get('transaction') or {}
        reference = event_data.get('reference') or transaction_data.get('reference')
        payment = LiveClassPayment.objects.filter(transaction_reference=reference).select_related('registration').first()
        if not payment:
            return Response({'status': 'ignored'})
        if event_name == 'charge.success':
            verify_live_class_payment(payment.registration, reference)
        elif event_name in ('refund.processed', 'refund.processing'):
            with transaction.atomic():
                payment.status = 'refunded'
                payment.save(update_fields=('status', 'updated_at'))
                registration = payment.registration
                registration.access_status = 'refunded'
                registration.save(update_fields=('access_status',))
        return Response({'status': 'ok'})


class MyLiveClassesView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = LiveClassRegistrationSerializer

    def get_queryset(self):
        return LiveClassRegistration.objects.filter(learner=self.request.user).select_related(
            'live_class', 'live_class__educator'
        ).order_by('live_class__scheduled_date', 'live_class__scheduled_time')


class JoinLiveClassView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, slug):
        live_class = get_object_or_404(LiveClass, slug=slug)
        role, registration = authorize_classroom(live_class, request.user)
        if not live_class.is_joinable():
            raise PermissionDenied('The classroom is outside its join window.')
        provider = CloudflareRealtimeKitV1()
        previous_id = (
            live_class.cloudflare_host_participant_id
            if role == 'host'
            else registration.cloudflare_participant_id
        )
        participant_id, token = provider.participant_token(live_class, request.user, role, previous_id)
        if role == 'host':
            live_class.cloudflare_host_participant_id = participant_id
            if live_class.status == 'published':
                live_class.status = 'live'
            live_class.save(update_fields=('cloudflare_host_participant_id', 'status', 'updated_at'))
        else:
            registration.cloudflare_participant_id = participant_id
            registration.save(update_fields=('cloudflare_participant_id',))

        visit = LiveClassAttendance.objects.create(live_class=live_class, learner=request.user)
        return Response({
            'auth_token': token,
            'meeting_id': live_class.cloudflare_meeting_id,
            'room_name': live_class.cloudflare_meeting_id,
            'participant_id': participant_id,
            'attendance_id': visit.id,
            'role': role,
        })


class LeaveLiveClassView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, slug):
        visit = get_object_or_404(
            LiveClassAttendance,
            pk=request.data.get('attendance_id'),
            live_class__slug=slug,
            learner=request.user,
        )
        visit.close()
        return Response(AttendanceSerializer(visit).data)


class EducatorLiveClassAnalyticsView(APIView):
    permission_classes = (IsAuthenticated, IsEducator)

    def get(self, request, slug):
        live_class = get_object_or_404(LiveClass, slug=slug, educator=request.user)
        registered = live_class.registrations.filter(access_status='active').count()
        attendees = live_class.attendance_visits.values('learner_id').distinct().count()
        total_duration = live_class.attendance_visits.aggregate(total=Sum('duration_seconds'))['total'] or 0
        return Response({
            'registered_count': registered,
            'attended_count': attendees,
            'attendance_rate': round((attendees / registered * 100), 1) if registered else 0,
            'average_attendance_seconds': round(total_duration / attendees) if attendees else 0,
            'visits': AttendanceSerializer(
                live_class.attendance_visits.select_related('learner'), many=True
            ).data,
        })


class LiveClassRecordingsView(generics.ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = RecordingSerializer

    def get_queryset(self):
        live_class = get_object_or_404(LiveClass, slug=self.kwargs['slug'])
        authorize_classroom(live_class, self.request.user)
        if live_class.cloudflare_meeting_id:
            provider = CloudflareRealtimeKitV1()
            for provider_recording in provider.list_recordings(live_class.cloudflare_meeting_id):
                provider_status = provider_recording.get('status')
                mapped_status = 'available' if provider_status == 'UPLOADED' else 'failed' if provider_status == 'ERRORED' else 'processing'
                LiveClassRecording.objects.update_or_create(
                    provider_recording_id=provider_recording['id'],
                    defaults={
                        'live_class': live_class,
                        'status': mapped_status,
                        'playback_url': provider_recording.get('download_url') or '',
                        'duration_seconds': int(provider_recording.get('recording_duration') or 0),
                        'available_at': timezone.now() if mapped_status == 'available' else None,
                    },
                )
        return live_class.recordings.filter(status='available')


class RecordingAccessView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, recording_id):
        recording = get_object_or_404(LiveClassRecording.objects.select_related('live_class'), pk=recording_id, status='available')
        authorize_classroom(recording.live_class, request.user)
        provider_data = CloudflareRealtimeKitV1().get_recording(recording.provider_recording_id)
        playback_url = provider_data.get('download_url') or recording.playback_url
        if not playback_url:
            return Response({'detail': 'Recording is not ready.'}, status=status.HTTP_409_CONFLICT)
        return Response({'playback_url': playback_url})
import hashlib
import hmac
import json

from django.conf import settings
from django.db import transaction

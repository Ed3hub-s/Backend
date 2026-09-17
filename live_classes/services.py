import logging
import uuid

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from .models import LiveClassPayment, LiveClassRegistration

logger = logging.getLogger(__name__)


class ProviderConfigurationError(APIException):
    status_code = 503
    default_detail = 'The live classroom provider is not configured.'


class CloudflareRealtimeKitV1:
    """Server-side gateway for the v1 RealtimeKit client integration."""

    timeout = 15

    def __init__(self):
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.app_id = settings.CLOUDFLARE_REALTIMEKIT_APP_ID
        self.api_token = settings.CLOUDFLARE_REALTIMEKIT_API_TOKEN
        if not all((self.account_id, self.app_id, self.api_token)):
            raise ProviderConfigurationError()
        self.base_url = (
            f'https://api.cloudflare.com/client/v4/accounts/{self.account_id}'
            f'/realtime/kit/{self.app_id}'
        )

    def _request(self, method, path, payload=None, params=None):
        try:
            response = requests.request(
                method,
                f'{self.base_url}{path}',
                headers={
                    'Authorization': f'Bearer {self.api_token}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.exception('Cloudflare RealtimeKit request failed')
            raise APIException('Cloudflare could not prepare the classroom. Please try again.') from exc
        if not body.get('success', True):
            raise APIException('Cloudflare rejected the classroom request.')
        return body.get('data') or body.get('result') or {}

    def list_recordings(self, meeting_id):
        data = self._request('GET', '/recordings', params={'meeting_id': meeting_id, 'per_page': 100})
        return data if isinstance(data, list) else data.get('recordings', [])

    def get_recording(self, recording_id):
        return self._request('GET', f'/recordings/{recording_id}')

    def create_meeting(self, live_class):
        data = self._request(
            'POST',
            '/meetings',
            {
                'title': live_class.title,
                'persist_chat': True,
                'record_on_start': live_class.recording_enabled,
            },
        )
        live_class.cloudflare_meeting_id = str(data['id'])
        live_class.save(update_fields=('cloudflare_meeting_id', 'updated_at'))
        return live_class.cloudflare_meeting_id

    def ensure_meeting(self, live_class):
        return live_class.cloudflare_meeting_id or self.create_meeting(live_class)

    def participant_token(self, live_class, user, role, participant_id=''):
        meeting_id = self.ensure_meeting(live_class)
        if participant_id:
            try:
                data = self._request(
                    'POST',
                    f'/meetings/{meeting_id}/participants/{participant_id}/token',
                    {},
                )
                token = data.get('token') or data.get('authToken')
                if token:
                    return participant_id, token
            except APIException:
                logger.info('Refreshing participant failed; creating a replacement participant')

        full_name = user.get_full_name().strip() or user.username
        data = self._request(
            'POST',
            f'/meetings/{meeting_id}/participants',
            {
                'name': full_name,
                'preset_name': (
                    settings.CLOUDFLARE_REALTIMEKIT_INSTRUCTOR_PRESET
                    if role == 'host'
                    else settings.CLOUDFLARE_REALTIMEKIT_STUDENT_PRESET
                ),
                'custom_participant_id': f'ed3hub-{live_class.pk}-{user.pk}-{uuid.uuid4().hex[:10]}',
            },
        )
        token = data.get('token') or data.get('authToken')
        if not token:
            raise APIException('Cloudflare did not return a classroom token.')
        return str(data['id']), token


def _initialize_paystack(user, live_class, reference):
    if not settings.PAYSTACK_SECRET_KEY:
        raise ProviderConfigurationError('Paystack is not configured for paid live classes.')
    callback_url = f"{settings.FRONTEND_URL.rstrip('/')}/live-classes/{live_class.slug}?payment=verify"
    try:
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
            json={
                'email': user.email,
                'amount': int(live_class.price * 100),
                'currency': live_class.currency,
                'reference': reference,
                'callback_url': callback_url,
                'metadata': {'live_class_id': live_class.id, 'user_id': user.id},
            },
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise APIException('Payment checkout could not be started. Please try again.') from exc
    if not body.get('status'):
        raise APIException(body.get('message', 'Paystack rejected the payment request.'))
    return body['data']


@transaction.atomic
def register_for_live_class(live_class, learner):
    locked_class = type(live_class).objects.select_for_update().get(pk=live_class.pk)
    existing = LiveClassRegistration.objects.filter(live_class=locked_class, learner=learner).first()
    if existing:
        if existing.access_status == 'active':
            return existing, None, False
        if existing.access_status not in ('pending',):
            raise ValidationError('This registration is no longer eligible for activation.')
        if existing.payment and existing.payment.status == 'pending':
            checkout = _initialize_paystack(learner, locked_class, existing.payment.transaction_reference)
            return existing, checkout, False

    active_count = locked_class.registrations.filter(access_status__in=('active', 'pending')).count()
    if active_count >= locked_class.capacity:
        raise ValidationError('This live class is full.')
    if locked_class.status != 'published' or locked_class.ends_at <= timezone.now():
        raise ValidationError('This live class is not open for registration.')
    if locked_class.educator_id == learner.id:
        raise ValidationError('Educators do not register for their own class.')

    if locked_class.access_type == 'free':
        registration = LiveClassRegistration.objects.create(
            live_class=locked_class,
            learner=learner,
            registration_status='confirmed',
            access_status='active',
            access_granted_at=timezone.now(),
        )
        return registration, None, True

    payment = LiveClassPayment.objects.create(
        user=learner,
        amount=locked_class.price,
        currency=locked_class.currency,
        transaction_reference=f'LC-{locked_class.pk}-{learner.pk}-{uuid.uuid4().hex[:16]}',
        metadata={'live_class_id': locked_class.pk},
    )
    registration = LiveClassRegistration.objects.create(
        live_class=locked_class,
        learner=learner,
        payment=payment,
    )
    checkout = _initialize_paystack(learner, locked_class, payment.transaction_reference)
    return registration, checkout, True


@transaction.atomic
def verify_live_class_payment(registration, reference):
    registration = LiveClassRegistration.objects.select_for_update().select_related('payment', 'live_class').get(
        pk=registration.pk
    )
    if not registration.payment or registration.payment.transaction_reference != reference:
        raise ValidationError('Payment reference does not match this registration.')
    if registration.access_status == 'active' and registration.payment.status == 'successful':
        return registration
    if not settings.PAYSTACK_SECRET_KEY:
        raise ProviderConfigurationError('Paystack is not configured.')
    try:
        response = requests.get(
            f'https://api.paystack.co/transaction/verify/{reference}',
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise APIException('Payment could not be verified. Please try again.') from exc
    data = body.get('data') or {}
    paid_amount = int(data.get('amount', 0))
    if data.get('status') != 'success' or paid_amount != int(registration.live_class.price * 100):
        raise ValidationError('Payment is not successful or the amount is incorrect.')

    payment = registration.payment
    payment.status = 'successful'
    payment.paid_at = timezone.now()
    payment.metadata = data
    payment.save(update_fields=('status', 'paid_at', 'metadata', 'updated_at'))
    registration.registration_status = 'confirmed'
    registration.access_status = 'active'
    registration.amount_paid = registration.live_class.price
    registration.access_granted_at = timezone.now()
    registration.save(
        update_fields=('registration_status', 'access_status', 'amount_paid', 'access_granted_at')
    )
    return registration


def authorize_classroom(live_class, user):
    if live_class.educator_id == user.id:
        return 'host', None
    registration = LiveClassRegistration.objects.filter(live_class=live_class, learner=user).first()
    if not registration or registration.access_status != 'active':
        raise PermissionDenied('An active live-class registration is required.')
    return 'learner', registration

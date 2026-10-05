import logging
import uuid
from decimal import Decimal
from urllib.parse import quote, urlsplit

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from .models import LiveClass, LiveClassBundle, LiveClassPayment, LiveClassRegistration

logger = logging.getLogger(__name__)


class ProviderConfigurationError(APIException):
    status_code = 503
    default_detail = 'The live classroom provider is not configured.'


class ProviderResourceNotFound(APIException):
    status_code = 502
    default_detail = 'The classroom provider could not find the requested resource. Please contact support.'


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
        except requests.RequestException as exc:
            logger.exception('Cloudflare RealtimeKit request failed before a response was received')
            raise APIException('The classroom provider is temporarily unreachable. Please try again.') from exc

        try:
            body = response.json()
        except ValueError as exc:
            logger.error(
                'Cloudflare RealtimeKit returned a non-JSON response (status=%s, path=%s)',
                response.status_code,
                path,
            )
            raise APIException('The classroom provider returned an invalid response. Please try again.') from exc

        if not response.ok:
            provider_errors = body.get('errors') or []
            logger.error(
                'Cloudflare RealtimeKit rejected a request (status=%s, path=%s, errors=%s)',
                response.status_code,
                path,
                provider_errors,
            )
            if response.status_code in (401, 403):
                raise ProviderConfigurationError(
                    'The live classroom provider is not authorized to create classrooms. Please contact support.'
                )
            if response.status_code == 404:
                raise ProviderResourceNotFound()
            raise APIException('Cloudflare rejected the classroom request. Please try again.')
        if not body.get('success', True):
            logger.error('Cloudflare RealtimeKit request was unsuccessful (path=%s, errors=%s)', path, body.get('errors'))
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
        # Two first-time joins must never create different rooms for one class.
        # Read the identity again under a database lock, even for stale callers.
        with transaction.atomic():
            locked_class = LiveClass.objects.select_for_update().get(pk=live_class.pk)
            meeting_id = locked_class.cloudflare_meeting_id or self.create_meeting(locked_class)
        live_class.cloudflare_meeting_id = meeting_id
        return meeting_id

    def participant_preset(self, role):
        preset = (
            settings.CLOUDFLARE_REALTIMEKIT_INSTRUCTOR_PRESET
            if role == 'host'
            else settings.CLOUDFLARE_REALTIMEKIT_STUDENT_PRESET
        )
        # Existing deployments still have the old webinar defaults in their env.
        # Both roles must use GROUP_CALL for an interactive classroom; custom
        # preset names remain supported and must have matching media permissions.
        return {
            'webinar_presenter': 'group_call_host',
            'webinar_viewer': 'group_call_participant',
        }.get(preset, preset)

    def participant_token(self, live_class, user, role, participant_id=''):
        meeting_id = self.ensure_meeting(live_class)
        full_name = user.get_full_name().strip() or user.username
        preset = self.participant_preset(role)
        if participant_id:
            try:
                # Refreshing a token alone preserves the old viewer permissions.
                # Apply the current role before issuing a fresh token on rejoin.
                self._request(
                    'PATCH',
                    f'/meetings/{meeting_id}/participants/{participant_id}',
                    {'name': full_name, 'preset_name': preset},
                )
            except ProviderResourceNotFound:
                logger.info('Saved classroom participant no longer exists; creating a replacement')
            else:
                data = self._request(
                    'POST',
                    f'/meetings/{meeting_id}/participants/{participant_id}/token',
                    {},
                )
                token = data.get('token') or data.get('authToken')
                if token:
                    return participant_id, token
                raise APIException('Cloudflare did not return a classroom token.')

        data = self._request(
            'POST',
            f'/meetings/{meeting_id}/participants',
            {
                'name': full_name,
                'preset_name': preset,
                'custom_participant_id': f'ed3hub-{live_class.pk}-{user.pk}-{uuid.uuid4().hex[:10]}',
            },
        )
        token = data.get('token') or data.get('authToken')
        if not token:
            raise APIException('Cloudflare did not return a classroom token.')
        return str(data['id']), token


def _initialize_paystack(user, live_class, payment):
    if not settings.PAYSTACK_SECRET_KEY:
        raise ProviderConfigurationError('Paystack is not configured for paid live classes.')
    checkout = payment.metadata.get('checkout')
    if checkout:
        return checkout
    reference = payment.transaction_reference
    callback_url = f"{settings.FRONTEND_URL.rstrip('/')}/live-classes/{live_class.slug}?payment=verify"
    try:
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
            json={
                'email': payment.metadata.get('customer_email', user.email),
                'amount': int(payment.amount * 100),
                'currency': payment.currency,
                'reference': reference,
                'callback_url': callback_url,
                'metadata': {
                    'live_class_id': live_class.id, 'user_id': user.id,
                    'bundle_id': payment.metadata.get('bundle_id'),
                    'class_ids': payment.metadata.get('class_ids', [live_class.id]),
                },
            },
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise APIException('Payment checkout could not be started. Please try again.') from exc
    data = body.get('data') if isinstance(body, dict) else None
    if not isinstance(data, dict) or body.get('status') is not True:
        raise APIException('Paystack could not start checkout. Please try again.')
    url = urlsplit(data.get('authorization_url') or '')
    if data.get('reference') != reference or url.scheme != 'https' or url.hostname != 'checkout.paystack.com':
        raise APIException('Paystack returned an invalid checkout. Please contact support.')
    checkout = {'authorization_url': data['authorization_url'], 'reference': reference}
    payment.metadata = {**payment.metadata, 'checkout': checkout}
    payment.save(update_fields=('metadata', 'updated_at'))
    return checkout


@transaction.atomic
def register_for_live_class(live_class, learner):
    if live_class.bundle_id:
        return register_for_bundle(live_class, learner)
    locked_class = type(live_class).objects.select_for_update().get(pk=live_class.pk)
    if locked_class.bundle_id:
        raise ValidationError('This class was added to a bundle. Refresh and try again.')
    existing = LiveClassRegistration.objects.filter(live_class=locked_class, learner=learner).first()
    if locked_class.educator_id == learner.id:
        raise ValidationError('Educators do not register for their own class.')
    if existing and existing.access_status == 'active':
        authorize_classroom(locked_class, learner)
        return existing, None, False
    if locked_class.status not in ('published', 'live') or locked_class.ends_at <= timezone.now():
        raise ValidationError('This live class is not open for registration.')
    if existing:
        if existing.access_status not in ('pending',):
            raise ValidationError('This registration is no longer eligible for activation.')
        if existing.payment and existing.payment.status == 'pending':
            checkout = _initialize_paystack(learner, locked_class, existing.payment)
            return existing, checkout, False
        raise ValidationError('This registration requires support before another payment can be started.')

    active_count = locked_class.registrations.filter(access_status__in=('active', 'pending')).count()
    if active_count >= locked_class.capacity:
        raise ValidationError('This live class is full.')

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
        metadata={'live_class_id': locked_class.pk, 'customer_email': learner.email},
    )
    registration = LiveClassRegistration.objects.create(
        live_class=locked_class,
        learner=learner,
        payment=payment,
    )
    checkout = _initialize_paystack(learner, locked_class, payment)
    return registration, checkout, True


@transaction.atomic
def verify_live_class_payment(registration, reference):
    if registration.payment_id:
        LiveClassPayment.objects.select_for_update().get(pk=registration.payment_id)
    registration = LiveClassRegistration.objects.select_for_update().get(
        pk=registration.pk
    )
    if not registration.payment or registration.payment.transaction_reference != reference:
        raise ValidationError('Payment reference does not match this registration.')
    if registration.payment.user_id != registration.learner_id:
        raise ValidationError('Payment does not belong to this learner.')
    if registration.access_status in ('revoked', 'refunded', 'cancelled') or registration.payment.status == 'refunded':
        return registration
    if registration.access_status == 'active' and registration.payment.status == 'successful':
        return registration
    if not settings.PAYSTACK_SECRET_KEY:
        raise ProviderConfigurationError('Paystack is not configured.')
    try:
        response = requests.get(
            f'https://api.paystack.co/transaction/verify/{quote(reference, safe="")}',
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise APIException('Payment could not be verified. Please try again.') from exc
    payment = registration.payment
    data = body.get('data') if isinstance(body, dict) else None
    if not isinstance(data, dict) or body.get('status') is not True:
        raise APIException('Paystack could not verify this payment. Please try again.')
    customer = data.get('customer') or {}
    expected_email = payment.metadata.get('customer_email', payment.user.email)
    if (
        data.get('status') != 'success'
        or type(data.get('amount')) is not int
        or data['amount'] != int(payment.amount * 100)
        or data.get('currency') != payment.currency
        or data.get('reference') != payment.transaction_reference
        or not isinstance(customer, dict)
        or str(customer.get('email', '')).casefold() != expected_email.casefold()
    ):
        raise ValidationError('Payment is not yet successful or does not match this booking. Please check payment again or contact support.')

    payment.status = 'successful'
    payment.paid_at = timezone.now()
    # Keep checkout/invoice information; do not store reusable card authorizations.
    payment.metadata = {**payment.metadata, 'verified_transaction_id': data.get('id')}
    payment.save(update_fields=('status', 'paid_at', 'metadata', 'updated_at'))
    registrations = list(payment.registrations.select_for_update().order_by('live_class_id'))
    # Allocate the invoice once across its sessions, preserving every cent. This
    # keeps totals correct regardless of which session receives the callback.
    share, remainder = divmod(int(payment.amount * 100), len(registrations))
    for index, item in enumerate(registrations):
        if item.access_status != 'pending' or item.learner_id != payment.user_id:
            continue
        item.registration_status = 'confirmed'
        item.access_status = 'active'
        item.access_granted_at = payment.paid_at
        item.amount_paid = Decimal(share + (index < remainder)) / 100
        item.save(update_fields=('registration_status', 'access_status', 'access_granted_at', 'amount_paid'))
    registration.refresh_from_db()
    return registration


def authorize_classroom(live_class, user):
    if live_class.educator_id == user.id:
        return 'host', None
    registration = LiveClassRegistration.objects.select_related('payment').filter(live_class=live_class, learner=user).first()
    if not registration or registration.access_status != 'active' or registration.registration_status != 'confirmed':
        raise PermissionDenied('An active live-class registration is required.')
    if live_class.access_type == 'paid' or live_class.bundle_id or registration.payment_id:
        if not registration.payment or registration.payment.status != 'successful' or registration.payment.user_id != user.pk:
            raise PermissionDenied('A verified successful payment is required for every classroom visit.')
    return 'learner', registration


@transaction.atomic
def register_for_bundle(live_class, learner):
    bundle = LiveClassBundle.objects.select_for_update().get(pk=live_class.bundle_id)
    classes = list(bundle.classes.select_for_update().order_by('pk'))
    if bundle.educator_id == learner.pk:
        raise ValidationError('Educators do not register for their own bundle.')
    if len(classes) < 2 or any(item.status not in ('published', 'live') or item.ends_at <= timezone.now() for item in classes):
        raise ValidationError('All bundle sessions must be open for registration.')
    registrations = list(LiveClassRegistration.objects.filter(live_class__in=classes, learner=learner).select_related('payment'))
    if registrations:
        if len(registrations) != len(classes) or len({item.payment_id for item in registrations}) != 1:
            raise ValidationError('An existing booking conflicts with this bundle. Please contact support.')
        selected = next(item for item in registrations if item.live_class_id == live_class.pk)
        if all(item.access_status == 'active' for item in registrations):
            authorize_classroom(live_class, learner)
            return selected, None, False
        if any(item.access_status != 'pending' for item in registrations) or not selected.payment or selected.payment.status != 'pending':
            raise ValidationError('This bundle booking is no longer eligible for payment.')
        return selected, _initialize_paystack(learner, live_class, selected.payment), False
    for item in classes:
        if item.registrations.filter(access_status__in=('active', 'pending')).count() >= item.capacity:
            raise ValidationError(f'The bundle session {item.title} is full.')
    payment = LiveClassPayment.objects.create(
        user=learner, amount=bundle.price, currency=bundle.currency,
        transaction_reference=f'BUNDLE-{bundle.pk}-{uuid.uuid4().hex}',
        metadata={'bundle_id': bundle.pk, 'class_ids': [item.pk for item in classes], 'customer_email': learner.email},
    )
    for item in classes:
        registration = LiveClassRegistration.objects.create(live_class=item, learner=learner, payment=payment)
        if item.pk == live_class.pk:
            selected = registration
    return selected, _initialize_paystack(learner, live_class, payment), True

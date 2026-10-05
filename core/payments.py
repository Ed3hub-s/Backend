from urllib.parse import quote, urlsplit

import requests
from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError


def paystack_request(method, path, payload=None):
    if not settings.PAYSTACK_SECRET_KEY:
        error = APIException('Paystack is not configured. Please contact support.')
        error.status_code = 503
        raise error
    try:
        response = requests.request(
            method, f'https://api.paystack.co/{path}',
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
            json=payload, timeout=15,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise APIException('Paystack is temporarily unavailable. Please retry.') from exc
    if not isinstance(body, dict) or body.get('status') is not True or not isinstance(body.get('data'), dict):
        raise APIException('Paystack returned an invalid response. Please retry.')
    return body['data']


def initialize_payment(payment, callback_url):
    if payment.checkout:
        return payment.checkout
    data = paystack_request('POST', 'transaction/initialize', {
        'email': payment.customer_email, 'amount': int(payment.amount * 100),
        'currency': payment.currency, 'reference': payment.reference,
        'callback_url': callback_url,
        'metadata': {'course_id': payment.course_id, 'user_id': payment.learner_id},
    })
    checkout_url = urlsplit(data.get('authorization_url') or '')
    if data.get('reference') != payment.reference or checkout_url.scheme != 'https' or checkout_url.hostname != 'checkout.paystack.com':
        raise APIException('Paystack returned an invalid checkout.')
    payment.checkout = {'authorization_url': data['authorization_url'], 'reference': payment.reference}
    payment.save(update_fields=('checkout',))
    return payment.checkout


def verify_payment(payment):
    reference = quote(payment.reference, safe='')
    data = paystack_request('GET', f'transaction/verify/{reference}')
    customer = data.get('customer')
    if (
        data.get('status') != 'success'
        or type(data.get('amount')) is not int
        or data['amount'] != int(payment.amount * 100)
        or data.get('currency') != payment.currency
        or data.get('reference') != payment.reference
        or not isinstance(customer, dict)
        or str(customer.get('email', '')).casefold() != payment.customer_email.casefold()
    ):
        raise ValidationError('Payment is not successful or does not match this purchase.')
    return data

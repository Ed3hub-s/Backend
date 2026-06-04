import logging
import random
from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils.html import escape
from django.utils import timezone

from .models import (
    AffiliateMarketer,
    AffiliateReferral,
    MarketerTransaction,
    MarketerWallet,
    OTPCode,
)
from .email_utils import build_branded_email_html, build_plain_email_from_html, send_smart_email

logger = logging.getLogger(__name__)

MARKETER_SIGNUP_BONUS = Decimal('5.00')
MARKETER_FIRST_PURCHASE_COMMISSION_RATE = Decimal('0.20')

OTP_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 30px;">
  <div style="max-width: 480px; margin: auto; background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
    <h2 style="color: #0077ff; margin-bottom: 4px;">Ed3Hub</h2>
    <p style="color: #333; font-size: 15px;">Hi there,</p>
    <p style="color: #333; font-size: 15px;">Use the OTP below to verify your email address. It expires in <strong>10 minutes</strong>.</p>
    <div style="text-align: center; margin: 28px 0;">
      <span style="display: inline-block; font-size: 36px; font-weight: bold; letter-spacing: 10px; color: #0077ff; background: #f0f7ff; padding: 16px 28px; border-radius: 10px;">
        {code}
      </span>
    </div>
    <p style="color: #888; font-size: 13px;">If you did not request this, please ignore this email.</p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
    <p style="color: #bbb; font-size: 12px; text-align: center;">&copy; Ed3Hub. All rights reserved.</p>
  </div>
</body>
</html>
"""


def _send_otp_email(to_mail: str, mail_subject: str, html_message: str):
    try:
        send_smart_email(
            subject=mail_subject,
            body='',
            recipient_list=[to_mail],
            html_message=html_message,
        )
        logger.info(f'OTP email sent to {to_mail}')
    except Exception as e:
        logger.error(f'Failed to send OTP email to {to_mail}: {e}')
        raise


RESET_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; background: #f4f4f4; padding: 30px;">
  <div style="max-width: 480px; margin: auto; background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
    <h2 style="color: #0077ff; margin-bottom: 4px;">Ed3Hub</h2>
    <p style="color: #333; font-size: 15px;">Hi there,</p>
    <p style="color: #333; font-size: 15px;">Use the OTP below to reset your password. It expires in <strong>10 minutes</strong>.</p>
    <div style="text-align: center; margin: 28px 0;">
      <span style="display: inline-block; font-size: 36px; font-weight: bold; letter-spacing: 10px; color: #0077ff; background: #f0f7ff; padding: 16px 28px; border-radius: 10px;">
        {code}
      </span>
    </div>
    <p style="color: #888; font-size: 13px;">If you did not request this, please ignore this email.</p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
    <p style="color: #bbb; font-size: 12px; text-align: center;">&copy; Ed3Hub. All rights reserved.</p>
  </div>
</body>
</html>
"""


def create_and_send_reset_otp(email: str) -> str:
    OTPCode.objects.filter(email=email).delete()
    code = str(random.randint(100000, 999999))
    OTPCode.objects.create(
        email=email,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    html_message = RESET_HTML_TEMPLATE.format(code=code)
    _send_otp_email(email, 'Reset Your Ed3Hub Password', html_message)
    return code


def create_and_send_otp(email: str) -> str:
    OTPCode.objects.filter(email=email).delete()
    code = str(random.randint(100000, 999999))
    OTPCode.objects.create(
        email=email,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    html_message = OTP_HTML_TEMPLATE.format(code=code)
    _send_otp_email(email, 'Your Ed3Hub Verification Code', html_message)
    return code


def _welcome_first_name(user) -> str:
    display_name = (user.first_name or user.username or user.email or 'there').strip()
    return display_name.split()[0] if display_name else 'there'


def _welcome_body_html(user, role: str) -> str:
    first_name = escape(_welcome_first_name(user))
    support_email = getattr(settings, 'SUPPORT_EMAIL', getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@ed3hub.com'))

    if role == 'educator':
        return f"""
<p>Hi {first_name}, we noticed you just joined Ed3hub as a course creator.</p>
<p>Welcome aboard.</p>
<p>We're glad to have you here.</p>
<p>You're now part of a platform built for one core purpose: turning expertise into structured learning experiences that create real impact -- not just content sitting on the internet.</p>
<p>Your journey starts here:</p>
<ul>
  <li>Set up your educator profile</li>
  <li>Create and publish curated courses or bootcamps</li>
  <li>Share your knowledge with motivated learners</li>
  <li>Build a teaching presence that compounds in influence and opportunity over time</li>
</ul>
<p>We've designed the system to keep things simple. The complexity is in the ideas -- not the tools.</p>
<p>We'll give you the structure. You bring the expertise. Together, we make it usable for learners.</p>
<p>And if at any point you feel like you're "just setting things up"... that's normal. Most great educators start exactly there.</p>
<p>Welcome to Ed3hub. We're looking forward to what you'll teach the world.</p>
"""

    return f"""
<p>Hi {first_name},</p>
<p>Welcome to Ed3hub we're glad you're here.</p>
<p>You just made a great decision. Ed3hub is built around one simple idea: practical, structured learning that leads to real skill development not just passive content consumption.</p>
<p>Here's what's waiting for you:</p>
<ul>
  <li>Curated courses and bootcamps designed for real results</li>
  <li>A guided structure that lets you learn at your own pace</li>
  <li>A community of peers on the same path</li>
  <li>Skills that compound the more you show up</li>
</ul>
<p>You don't need to have it all figured out from day one. Just log in, look around, and take that first step. Everything else will follow.</p>
<p>And if anything feels unclear along the way -- good. Confusion is just your brain making room for something new. Sit with it briefly, then keep moving.</p>
<p>We try to keep things simple here. The only complexity we allow is in your growth.</p>
<p>Need help or have questions? We're always a message away at <a href="mailto:{escape(support_email)}">{escape(support_email)}</a>.</p>
"""


def send_welcome_email(user, role: str | None = None, fail_silently: bool = True) -> bool:
    if not user.email:
        return False

    role = role or getattr(getattr(user, 'profile', None), 'role', 'learner')
    if role not in ('learner', 'educator'):
        role = 'learner'

    subject = "Welcome to Ed3hub let's get to work"
    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://ed3hub.com').rstrip('/')
    dashboard_path = '/dashboard' if role == 'educator' else '/learner-dashboard'
    html_message = build_branded_email_html(
        subject=subject,
        body_html=_welcome_body_html(user, role),
        preheader='Welcome to Ed3hub. Your account is ready.',
        header_title='Welcome to Ed3hub',
        header_subtitle="Let's get to work",
        cta_text='Get Started',
        cta_url=f'{frontend_url}{dashboard_path}',
        footer_note='You are receiving this email because you joined Ed3hub.',
    )
    plain_message = build_plain_email_from_html(
        _welcome_body_html(user, role),
        'You are receiving this email because you joined Ed3hub.',
    )

    try:
        return send_smart_email(
            subject=subject,
            body=plain_message,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=fail_silently,
        )
    except Exception as exc:
        logger.error(f'Failed to send welcome email to {user.email}: {exc}')
        if fail_silently:
            return False
        raise


def get_affiliate_marketer_by_code(referral_code):
    referral_code = (referral_code or '').strip()
    if not referral_code:
        return None
    return (
        AffiliateMarketer.objects
        .select_related('user')
        .filter(referral_code__iexact=referral_code, is_active=True, user__is_active=True)
        .first()
    )


def create_affiliate_referral(referred_user, referral_code):
    affiliate = get_affiliate_marketer_by_code(referral_code)
    if not affiliate or affiliate.user_id == referred_user.id:
        return None

    referral, _ = AffiliateReferral.objects.get_or_create(
        referred_user=referred_user,
        defaults={
            'marketer': affiliate.user,
            'referral_code': affiliate.referral_code,
        },
    )
    return referral


def credit_verified_referral_signup(user):
    try:
        referral = AffiliateReferral.objects.select_related('marketer', 'referred_user').get(referred_user=user)
    except AffiliateReferral.DoesNotExist:
        return None

    with transaction.atomic():
        referral = AffiliateReferral.objects.select_for_update().get(id=referral.id)
        if referral.signup_bonus_paid:
            return referral

        wallet, _ = MarketerWallet.objects.select_for_update().get_or_create(marketer=referral.marketer)
        wallet.balance = Decimal(str(wallet.balance)) + MARKETER_SIGNUP_BONUS
        wallet.total_earned = Decimal(str(wallet.total_earned)) + MARKETER_SIGNUP_BONUS
        wallet.save(update_fields=['balance', 'total_earned', 'updated_at'])

        MarketerTransaction.objects.create(
            wallet=wallet,
            referral=referral,
            referred_user=referral.referred_user,
            amount=MARKETER_SIGNUP_BONUS,
            transaction_type='signup_bonus',
            description=f'Signup bonus for referring {referral.referred_user.username}',
        )
        referral.signup_bonus_paid = True
        referral.save(update_fields=['signup_bonus_paid'])
        return referral


def credit_first_purchase_commission(user, course):
    if not course or course.is_free:
        return None

    try:
        price = Decimal(str(course.price)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError):
        return None
    if price <= 0:
        return None

    try:
        referral = AffiliateReferral.objects.select_related('marketer', 'referred_user').get(referred_user=user)
    except AffiliateReferral.DoesNotExist:
        return None

    with transaction.atomic():
        referral = AffiliateReferral.objects.select_for_update().get(id=referral.id)
        if referral.first_purchase_reward_paid:
            return referral

        commission = (price * MARKETER_FIRST_PURCHASE_COMMISSION_RATE).quantize(Decimal('0.01'))
        wallet, _ = MarketerWallet.objects.select_for_update().get_or_create(marketer=referral.marketer)
        wallet.balance = Decimal(str(wallet.balance)) + commission
        wallet.total_earned = Decimal(str(wallet.total_earned)) + commission
        wallet.save(update_fields=['balance', 'total_earned', 'updated_at'])

        MarketerTransaction.objects.create(
            wallet=wallet,
            referral=referral,
            referred_user=referral.referred_user,
            course=course,
            amount=commission,
            transaction_type='purchase_commission',
            description=f'20% first purchase commission from {referral.referred_user.username} buying "{course.title}"',
        )
        referral.first_purchase_reward_paid = True
        referral.first_purchase_course = course
        referral.first_purchase_amount = price
        referral.first_purchase_commission = commission
        referral.first_purchase_at = timezone.now()
        referral.save(update_fields=[
            'first_purchase_reward_paid',
            'first_purchase_course',
            'first_purchase_amount',
            'first_purchase_commission',
            'first_purchase_at',
        ])
        return referral

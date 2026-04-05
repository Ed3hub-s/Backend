import logging
import random
import sys
import threading
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import OTPCode

logger = logging.getLogger(__name__)

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


def _send_in_background(to_mail: str, mail_subject: str, html_message: str):
    """Sends email in a background thread using credentials from settings."""
    try:
        email_sent = send_mail(
            subject=mail_subject,
            message='',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[to_mail],
            html_message=html_message,
            fail_silently=False,
        )
        if email_sent:
            logger.info(f'OTP email sent to {to_mail}')
        else:
            logger.warning(f'OTP email not sent to {to_mail}')
    except Exception as e:
        logger.error(f'Failed to send OTP email to {to_mail}: {e}')


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

    msg = f'\n========== PASSWORD RESET OTP FOR {email} ==========\nCode: {code}\n====================================================\n'
    sys.stdout.write(msg)
    sys.stdout.flush()
    print(msg, flush=True)

    html_message = RESET_HTML_TEMPLATE.format(code=code)
    threading.Thread(
        target=_send_in_background,
        args=(email, 'Reset Your Ed3Hub Password', html_message),
        daemon=True,
    ).start()
    return code


def create_and_send_otp(email: str) -> str:
    OTPCode.objects.filter(email=email).delete()
    code = str(random.randint(100000, 999999))
    OTPCode.objects.create(
        email=email,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=10),
    )

    msg = f'\n========== OTP FOR {email} ==========\nCode: {code}\n=====================================\n'
    sys.stdout.write(msg)
    sys.stdout.flush()
    print(msg, flush=True)

    html_message = OTP_HTML_TEMPLATE.format(code=code)
    threading.Thread(
        target=_send_in_background,
        args=(email, 'Your Ed3Hub Verification Code', html_message),
        daemon=True,
    ).start()

    return code

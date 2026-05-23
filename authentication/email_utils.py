import logging
from django.conf import settings
from django.utils.html import escape, strip_tags
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)


def build_branded_email_html(
    *,
    subject: str,
    body_html: str,
    preheader: str = '',
    header_title: str = 'Ed3Hub',
    header_subtitle: str = 'Learn. Build. Own your future.',
    footer_note: str = '',
    cta_text: str = '',
    cta_url: str = '',
) -> str:
    """Wrap email content with Ed3Hub header, footer, and signature."""
    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://ed3hub.com').rstrip('/')
    footer_note = footer_note or (
        'You are receiving this email because you joined Ed3Hub as a learner or educator.'
    )
    safe_body = mark_safe(body_html or '')
    safe_subject = escape(subject)
    safe_preheader = escape(preheader)
    safe_header_title = escape(header_title)
    safe_header_subtitle = escape(header_subtitle)
    safe_footer_note = escape(footer_note)
    safe_cta_text = escape(cta_text)
    safe_cta_url = escape(cta_url)
    cta_markup = ''
    if cta_text and cta_url:
        cta_markup = f'''
          <div style="margin: 28px 0;">
            <a href="{safe_cta_url}" style="display: inline-block; background: #2563eb; color: #ffffff; text-decoration: none; padding: 12px 18px; border-radius: 10px; font-weight: 700;">
              {safe_cta_text}
            </a>
          </div>
        '''

    return f'''<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{safe_subject}</title>
  </head>
  <body style="margin: 0; padding: 0; background: #f3f4f6; color: #111827; font-family: Arial, Helvetica, sans-serif;">
    <div style="display: none; max-height: 0; overflow: hidden; opacity: 0;">{safe_preheader}</div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: #f3f4f6; padding: 24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 640px; background: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e5e7eb;">
            <tr>
              <td style="background: #0f172a; color: #ffffff; padding: 28px 32px;">
                <div style="font-size: 24px; font-weight: 800; letter-spacing: 0;">{safe_header_title}</div>
                <div style="margin-top: 6px; color: #cbd5e1; font-size: 14px;">{safe_header_subtitle}</div>
              </td>
            </tr>
            <tr>
              <td style="padding: 32px; font-size: 15px; line-height: 1.7; color: #1f2937;">
                {safe_body}
                {cta_markup}
              </td>
            </tr>
            <tr>
              <td style="padding: 24px 32px; background: #f9fafb; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px; line-height: 1.6;">
                <p style="margin: 0 0 12px;">Warm regards,<br><strong style="color: #111827;">The Ed3Hub Team</strong></p>
                <p style="margin: 0 0 12px;">{safe_footer_note}</p>
                <p style="margin: 0;">
                  <a href="{frontend_url}" style="color: #2563eb; text-decoration: none;">Visit Ed3Hub</a>
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>'''


def build_plain_email_from_html(body_html: str, footer_note: str = '') -> str:
    footer_note = footer_note or 'You are receiving this email because you joined Ed3Hub.'
    body = strip_tags(body_html or '').strip()
    return f'{body}\n\nWarm regards,\nThe Ed3Hub Team\n\n{footer_note}'.strip()


def send_smart_email(subject: str, body: str, recipient_list: list,
                     html_message: str = '', fail_silently: bool = False) -> bool:
    """
    Send email via SendGrid API. Falls back to SMTP if SENDGRID_API_KEY is not set.
    """
    api_key = getattr(settings, 'SENDGRID_API_KEY', None)

    if api_key:
        return _send_via_sendgrid(api_key, subject, body, recipient_list, html_message, fail_silently)
    else:
        return _send_via_smtp(subject, body, recipient_list, html_message, fail_silently)


def _send_via_sendgrid(api_key: str, subject: str, body: str, recipient_list: list,
                       html_message: str, fail_silently: bool) -> bool:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, To, Content

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@ed3hub.com')

        message = Mail(
            from_email=from_email,
            to_emails=[To(r) for r in recipient_list],
            subject=subject,
        )

        if html_message:
            message.content = [
                Content('text/plain', body or ' '),
                Content('text/html', html_message),
            ]
        else:
            message.content = [Content('text/plain', body or ' ')]

        sg = SendGridAPIClient(api_key)
        response = sg.send(message)

        if response.status_code in (200, 202):
            logger.info(f'SendGrid: email sent to {recipient_list} (status {response.status_code})')
            return True
        else:
            msg = f'SendGrid returned status {response.status_code}: {response.body}'
            logger.error(msg)
            if fail_silently:
                return False
            raise ConnectionError(msg)

    except Exception as e:
        logger.error(f'SendGrid failed: {e}')
        if fail_silently:
            return False
        raise


def _send_via_smtp(subject: str, body: str, recipient_list: list,
                   html_message: str, fail_silently: bool) -> bool:
    """SMTP fallback with auto port detection."""
    import socket
    import smtplib
    import ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    host = getattr(settings, 'EMAIL_HOST', '')
    username = getattr(settings, 'EMAIL_HOST_USER', '')
    password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', username)
    timeout = getattr(settings, 'EMAIL_TIMEOUT', 10)

    CONFIGS = [
        {'port': 587,  'use_ssl': False, 'use_tls': True},
        {'port': 465,  'use_ssl': True,  'use_tls': False},
        {'port': 2525, 'use_ssl': False, 'use_tls': True},
    ]

    def port_open(port):
        try:
            s = socket.socket()
            s.settimeout(5)
            result = s.connect_ex((host, port))
            s.close()
            return result == 0
        except Exception:
            return False

    for cfg in CONFIGS:
        if not port_open(cfg['port']):
            continue
        try:
            if cfg['use_ssl']:
                server = smtplib.SMTP_SSL(host, cfg['port'], context=ssl.create_default_context(), timeout=timeout)
            else:
                server = smtplib.SMTP(host, cfg['port'], timeout=timeout)
                server.ehlo()
                if cfg['use_tls']:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()

            if username and password:
                server.login(username, password)

            if html_message:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = from_email
                msg['To'] = ', '.join(recipient_list)
                msg.attach(MIMEText(body or '', 'plain'))
                msg.attach(MIMEText(html_message, 'html'))
            else:
                msg = MIMEMultipart()
                msg['Subject'] = subject
                msg['From'] = from_email
                msg['To'] = ', '.join(recipient_list)
                msg.attach(MIMEText(body or '', 'plain'))

            server.sendmail(from_email, recipient_list, msg.as_string())
            server.quit()
            logger.info(f'SMTP port {cfg["port"]}: email sent to {recipient_list}')
            return True
        except Exception as e:
            logger.warning(f'SMTP port {cfg["port"]} failed: {e}')

    msg = f'All email methods failed for recipients: {recipient_list}'
    logger.error(msg)
    if fail_silently:
        return False
    raise ConnectionError(msg)

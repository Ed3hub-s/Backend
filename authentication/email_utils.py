import logging
from django.conf import settings

logger = logging.getLogger(__name__)


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

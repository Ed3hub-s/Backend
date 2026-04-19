import socket
import smtplib
import ssl
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# All port/TLS combinations to try in order of preference
SMTP_CONFIGS = [
    {'port': 587, 'use_tls': True,  'use_ssl': False, 'label': '587/STARTTLS'},
    {'port': 465, 'use_tls': False, 'use_ssl': True,  'label': '465/SSL'},
    {'port': 2525, 'use_tls': True, 'use_ssl': False, 'label': '2525/STARTTLS'},
    {'port': 25,  'use_tls': False, 'use_ssl': False, 'label': '25/plain'},
]


def _port_open(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def _try_send(host: str, cfg: dict, username: str, password: str,
              from_email: str, recipient_list: list,
              subject: str, body: str, html_message: str = '') -> bool:
    """Attempt to send using a specific port/TLS config. Returns True on success."""
    timeout = getattr(settings, 'EMAIL_TIMEOUT', 10)
    try:
        if cfg['use_ssl']:
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(host, cfg['port'], context=ctx, timeout=timeout)
        else:
            server = smtplib.SMTP(host, cfg['port'], timeout=timeout)
            server.ehlo()
            if cfg['use_tls']:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()

        if username and password:
            server.login(username, password)

        # Build MIME message
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

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
        return True
    except Exception as e:
        logger.warning(f'SMTP {cfg["label"]} failed: {e}')
        return False


def send_smart_email(subject: str, body: str, recipient_list: list,
                     html_message: str = '', fail_silently: bool = False) -> bool:
    """
    Send an email by auto-detecting the working SMTP port.
    Tries all port/TLS combinations and uses the first one that works.
    Raises on failure unless fail_silently=True.
    """
    host = getattr(settings, 'EMAIL_HOST', '')
    username = getattr(settings, 'EMAIL_HOST_USER', '')
    password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', username)

    if not host:
        raise ValueError('EMAIL_HOST is not configured.')

    for cfg in SMTP_CONFIGS:
        if not _port_open(host, cfg['port']):
            logger.info(f'Port {cfg["port"]} is blocked, skipping.')
            continue

        logger.info(f'Port {cfg["port"]} is open, trying {cfg["label"]}...')
        success = _try_send(
            host, cfg, username, password,
            from_email, recipient_list,
            subject, body, html_message,
        )
        if success:
            logger.info(f'Email sent successfully via {cfg["label"]}')
            return True

    msg = f'All SMTP ports blocked or failed for host: {host}'
    logger.error(msg)
    if fail_silently:
        return False
    raise ConnectionError(msg)

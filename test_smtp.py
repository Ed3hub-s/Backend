"""
Run: python test_smtp.py
Tests all SMTP ports and sends a test email using the first working one.
"""
import socket
import smtplib
import ssl

HOST     = 'das125.truehost.cloud'
USER     = 'ed3hub@ed3hub.name.ng'
PASSWORD = 'EIFousk4J0jqN9R4'
TO       = 'marketpointa@gmail.com'

CONFIGS = [
    {'port': 587,  'use_ssl': False, 'use_tls': True,  'label': '587/STARTTLS'},
    {'port': 465,  'use_ssl': True,  'use_tls': False, 'label': '465/SSL'},
    {'port': 2525, 'use_ssl': False, 'use_tls': True,  'label': '2525/STARTTLS'},
    {'port': 25,   'use_ssl': False, 'use_tls': False, 'label': '25/plain'},
]

print(f'Scanning ports on {HOST}...\n')
for cfg in CONFIGS:
    try:
        s = socket.socket()
        s.settimeout(5)
        result = s.connect_ex((HOST, cfg['port']))
        s.close()
        status = 'OPEN' if result == 0 else 'BLOCKED'
        print(f'  Port {cfg["port"]} ({cfg["label"]}): {status}')
    except Exception as e:
        print(f'  Port {cfg["port"]}: ERROR - {e}')

print(f'\nAttempting to send email to {TO}...\n')
for cfg in CONFIGS:
    try:
        s = socket.socket()
        s.settimeout(5)
        if s.connect_ex((HOST, cfg['port'])) != 0:
            s.close()
            continue
        s.close()

        print(f'  Trying {cfg["label"]}...', end=' ')
        if cfg['use_ssl']:
            ctx = ssl.create_default_context()
            server = smtplib.SMTP_SSL(HOST, cfg['port'], context=ctx, timeout=10)
        else:
            server = smtplib.SMTP(HOST, cfg['port'], timeout=10)
            server.ehlo()
            if cfg['use_tls']:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()

        server.login(USER, PASSWORD)
        msg = f'Subject: Ed3Hub SMTP Test ({cfg["label"]})\n\nWorking port: {cfg["port"]}'
        server.sendmail(USER, TO, msg)
        server.quit()
        print(f'SUCCESS')
        print(f'\n✓ Use PORT={cfg["port"]}, USE_SSL={cfg["use_ssl"]}, USE_TLS={cfg["use_tls"]}')
        break
    except Exception as e:
        print(f'FAILED - {e}')

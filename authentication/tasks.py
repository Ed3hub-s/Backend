from celery import shared_task

from .newsletter_delivery import send_due_newsletter_campaigns


@shared_task
def send_due_newsletters():
    return send_due_newsletter_campaigns()

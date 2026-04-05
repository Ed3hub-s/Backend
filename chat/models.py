from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserPresence(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='presence')
    last_seen = models.DateTimeField(default=timezone.now)

    def is_online(self):
        return (timezone.now() - self.last_seen).total_seconds() < 60

    def __str__(self):
        return f'{self.user.username} last_seen={self.last_seen}'


class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        names = ', '.join(u.username for u in self.participants.all())
        return f'Conversation({names})'


class Message(models.Model):
    TYPE_TEXT = 'text'
    TYPE_IMAGE = 'image'
    TYPE_FILE = 'file'
    TYPE_LINK = 'link'
    TYPE_CHOICES = [
        (TYPE_TEXT, 'Text'),
        (TYPE_IMAGE, 'Image'),
        (TYPE_FILE, 'File'),
        (TYPE_LINK, 'Link'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    msg_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_TEXT)
    text = models.TextField(blank=True, default='')
    file = models.FileField(upload_to='chat/files/', blank=True, null=True)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.text[:40] or self.msg_type}'


class Reaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reactions')
    emoji = models.CharField(max_length=10)

    class Meta:
        unique_together = ('message', 'user')

    def __str__(self):
        return f'{self.user.username} reacted {self.emoji}'

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CHOICES = (('learner', 'Learner'), ('educator', 'Educator'))
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='learner')
    bio = models.TextField(blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    city_country = models.CharField(max_length=100, blank=True, default='')
    specialization = models.CharField(max_length=255, blank=True, default='')
    experience = models.CharField(max_length=100, blank=True, default='')
    whatsapp = models.CharField(max_length=30, blank=True, default='')
    facebook = models.URLField(max_length=255, blank=True, default='')
    twitter_x = models.URLField(max_length=255, blank=True, default='')
    linkedin = models.URLField(max_length=255, blank=True, default='')
    instagram = models.URLField(max_length=255, blank=True, default='')

    def __str__(self):
        return f'{self.user.username} - {self.role}'


class OTPCode(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        return timezone.now() < self.expires_at

    def __str__(self):
        return f'{self.email} - {self.code}'

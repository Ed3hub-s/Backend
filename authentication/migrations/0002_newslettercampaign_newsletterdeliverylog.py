# Generated manually for newsletter campaigns.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsletterCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Internal name shown only in admin.', max_length=150)),
                ('subject', models.CharField(max_length=180)),
                ('preheader', models.CharField(blank=True, default='', help_text='Short preview text some inboxes show after the subject.', max_length=180)),
                ('audience', models.CharField(choices=[('all', 'Learners and educators'), ('learners', 'Learners only'), ('educators', 'Educators only')], default='all', max_length=16)),
                ('header_title', models.CharField(default='Ed3Hub Newsletter', max_length=120)),
                ('header_subtitle', models.CharField(default='Updates for learners and educators', max_length=180)),
                ('body_html', models.TextField(help_text='Main newsletter body. Simple HTML is allowed, for example <p>, <strong>, <ul>, and <a>.')),
                ('cta_text', models.CharField(blank=True, default='', max_length=80, verbose_name='Button text')),
                ('cta_url', models.URLField(blank=True, default='', verbose_name='Button URL')),
                ('footer_note', models.TextField(blank=True, default='You are receiving this email because you joined Ed3Hub as a learner or educator.')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('scheduled', 'Scheduled'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed')], default='draft', max_length=12)),
                ('scheduled_for', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('total_recipients', models.PositiveIntegerField(default=0)),
                ('successful_sends', models.PositiveIntegerField(default=0)),
                ('failed_sends', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True, default='')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='newsletters_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='NewsletterDeliveryLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[('sent', 'Sent'), ('failed', 'Failed')], max_length=8)),
                ('error', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_logs', to='authentication.newslettercampaign')),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
    ]

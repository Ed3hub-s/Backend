from django.db import migrations


def backfill_creator_completion_tokens(apps, schema_editor):
    Enrollment = apps.get_model('courses', 'Enrollment')
    TokenWallet = apps.get_model('courses', 'TokenWallet')
    TokenTransaction = apps.get_model('courses', 'TokenTransaction')

    completed_enrollments = Enrollment.objects.filter(completed=True).select_related(
        'learner',
        'course',
        'course__instructor',
    )

    for enrollment in completed_enrollments.iterator():
        course = enrollment.course
        if course.instructor_id == enrollment.learner_id:
            continue

        wallet, _ = TokenWallet.objects.get_or_create(learner_id=course.instructor_id)
        description = f'{enrollment.learner.username} completed your course: {course.title}'

        if TokenTransaction.objects.filter(
            wallet=wallet,
            amount=course.completion_tokens,
            reason='course_complete',
            description=description,
        ).exists():
            continue

        TokenTransaction.objects.create(
            wallet=wallet,
            amount=course.completion_tokens,
            reason='course_complete',
            description=description,
            is_claimed=False,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0002_educator_wallet'),
    ]

    operations = [
        migrations.RunPython(backfill_creator_completion_tokens, migrations.RunPython.noop),
    ]

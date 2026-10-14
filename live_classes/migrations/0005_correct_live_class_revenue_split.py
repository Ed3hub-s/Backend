from decimal import Decimal

from django.db import migrations


def correct_live_class_revenue_split(apps, schema_editor):
    LiveClassPayment = apps.get_model('live_classes', 'LiveClassPayment')
    LiveClassRegistration = apps.get_model('live_classes', 'LiveClassRegistration')
    EducatorWallet = apps.get_model('courses', 'EducatorWallet')
    EducatorTransaction = apps.get_model('courses', 'EducatorTransaction')

    for payment in LiveClassPayment.objects.filter(
        status='successful', educator_credited_at__isnull=False,
    ).iterator():
        target_share = (payment.amount * Decimal('0.80')).quantize(Decimal('0.01'))
        current_share = Decimal(str(payment.educator_share))
        adjustment = target_share - current_share
        if adjustment == 0:
            continue
        registration = LiveClassRegistration.objects.filter(
            payment_id=payment.pk,
        ).select_related('live_class').first()
        if not registration:
            continue
        wallet = EducatorWallet.objects.get(educator_id=registration.live_class.educator_id)
        wallet.balance = Decimal(str(wallet.balance)) + adjustment
        wallet.total_earned = Decimal(str(wallet.total_earned)) + adjustment
        wallet.save(update_fields=('balance', 'total_earned', 'updated_at'))
        EducatorTransaction.objects.create(
            wallet_id=wallet.pk,
            amount=abs(adjustment),
            transaction_type='credit' if adjustment > 0 else 'debit',
            course_id=registration.live_class.course_id,
            description=f'Live class revenue share adjustment to 80%: {registration.live_class.title}',
        )
        payment.educator_share = target_share
        payment.save(update_fields=('educator_share', 'updated_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('live_classes', '0004_liveclasspayment_educator_credited_at_and_more'),
    ]

    operations = [
        migrations.RunPython(correct_live_class_revenue_split, migrations.RunPython.noop),
    ]

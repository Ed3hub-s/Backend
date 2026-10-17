import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from authentication.utils import credit_first_purchase_commission
from core.payments import initialize_payment, verify_payment
from .models import Course, CoursePayment, Enrollment, EducatorWallet, EducatorTransaction, EDUCATOR_SHARE


def has_course_access(course, user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or course.instructor_id == user.pk:
        return True
    enrollments = Enrollment.objects.filter(course=course, learner=user)
    if course.is_free:
        return enrollments.exists()
    return enrollments.filter(payment__status='successful', payment__learner=user, payment__course=course).exists()


def require_course_access(course, user):
    if not has_course_access(course, user):
        raise PermissionDenied('Enrollment with a verified payment is required for this course.')


@transaction.atomic
def purchase_course(course, learner, reference=None):
    course = Course.objects.select_for_update().get(pk=course.pk)
    if not course.is_published:
        raise ValidationError('This course is not available for purchase.')
    if course.instructor_id == learner.pk:
        raise ValidationError('You already own this course.')
    if course.is_free:
        enrollment, created = Enrollment.objects.get_or_create(course=course, learner=learner)
        return enrollment, None, created
    if course.price <= 0:
        raise ValidationError('This paid course has no valid price. Please contact support.')
    if reference:
        payment = CoursePayment.objects.filter(course=course, learner=learner, reference=reference).first()
        if not payment:
            raise ValidationError('Payment reference does not match this course purchase.')
        return fulfill_course_payment(payment), None, False
    enrollment = Enrollment.objects.filter(course=course, learner=learner, payment__status='successful').first()
    if enrollment:
        return enrollment, None, False
    # Paystack authorization URLs are transaction-specific and may no longer be
    # usable after they have been opened, abandoned, or completed.  Reusing a
    # stored pending checkout therefore strands a learner on Paystack's
    # "link is incorrect or transaction is already completed" page.  Every
    # explicit checkout attempt gets its own immutable payment reference.
    payment = CoursePayment.objects.create(
        course=course, learner=learner, amount=course.price,
        customer_email=learner.email, reference=f'COURSE-{uuid.uuid4().hex}',
    )
    frontend_url = settings.FRONTEND_URL.rstrip('/')
    callback = f'{frontend_url}/courses/payment-return?course_id={course.pk}'
    return None, initialize_payment(payment, callback), False


@transaction.atomic
def fulfill_course_payment(payment):
    Course.objects.select_for_update().get(pk=payment.course_id)
    payment = CoursePayment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == 'refunded':
        raise ValidationError('This payment has been refunded.')
    if payment.status != 'successful':
        verify_payment(payment)
        payment.status = 'successful'
        payment.paid_at = timezone.now()
        payment.save(update_fields=('status', 'paid_at'))
    enrollment, created = Enrollment.objects.get_or_create(course=payment.course, learner=payment.learner)
    if enrollment.payment_id == payment.pk:
        return enrollment
    if enrollment.payment_id and enrollment.payment.status == 'successful':
        raise ValidationError('This course already has a different successful payment. Please contact support.')
    enrollment.payment = payment
    enrollment.save(update_fields=('payment',))
    share = (payment.amount * Decimal(str(EDUCATOR_SHARE))).quantize(Decimal('0.01'))
    wallet, _ = EducatorWallet.objects.select_for_update().get_or_create(educator=payment.course.instructor)
    wallet.balance = Decimal(str(wallet.balance)) + share
    wallet.total_earned = Decimal(str(wallet.total_earned)) + share
    wallet.save(update_fields=('balance', 'total_earned'))
    EducatorTransaction.objects.create(
        wallet=wallet, amount=share, transaction_type='credit', course=payment.course,
        description=f'Verified course payment {payment.reference}',
    )
    credit_first_purchase_commission(payment.learner, payment.course, paid_amount=payment.amount)
    return enrollment


@transaction.atomic
def refund_course_payment(payment):
    Course.objects.select_for_update().get(pk=payment.course_id)
    payment = CoursePayment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == 'refunded':
        return
    if payment.status == 'successful':
        share = (payment.amount * Decimal(str(EDUCATOR_SHARE))).quantize(Decimal('0.01'))
        wallet = EducatorWallet.objects.select_for_update().get(educator=payment.course.instructor)
        wallet.balance = Decimal(str(wallet.balance)) - share
        wallet.total_earned = Decimal(str(wallet.total_earned)) - share
        wallet.save(update_fields=('balance', 'total_earned'))
        EducatorTransaction.objects.create(
            wallet=wallet, amount=share, transaction_type='debit', course=payment.course,
            description=f'Refund for {payment.reference}',
        )
    payment.status = 'refunded'
    payment.save(update_fields=('status',))

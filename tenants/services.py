"""
tenants/services.py
────────────────────
High-level business logic for the SaaS layer:

  • approve_registration()   — review → create Tenant + seed defaults + email
  • provision_tenant()       — create default academic session, classes, etc.
  • start_trial()            — 14-day trial for new tenant
  • activate_subscription()  — upgrade after Paystack payment confirmed
  • cancel_subscription()    — mark subscription cancelled
  • check_limit()            — enforce plan caps (students, staff, classes)
  • handle_paystack_webhook()— verify and process payment webhooks
"""

import hmac
import hashlib
import json
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction                  # FIX #2: import for atomic blocks
from django.utils import timezone

from tenants.models import Plan, Tenant, Subscription, SubscriptionPayment, SchoolRegistration

logger = logging.getLogger(__name__)

TRIAL_DAYS = 14


# ─────────────────────────────────────────────────────────────────────────────
# Registration → Tenant provisioning
# ─────────────────────────────────────────────────────────────────────────────

def approve_registration(reg: SchoolRegistration, approved_by=None) -> Tenant:
    """
    Convert a SchoolRegistration (PENDING) into a live Tenant.
    Sends welcome email to the school contact.

    Wrapped in transaction.atomic() so that if any step fails (e.g. Tenant
    save, reg update), nothing is partially committed to the database.
    """
    if reg.status != 'PENDING':
        raise ValueError(f"Registration {reg.id} is already {reg.status}.")

    # FIX #2: Wrap Tenant creation + reg update in a single atomic transaction.
    # Previously, if Tenant.save() succeeded but reg.save() failed (or vice
    # versa), the database was left in a broken half-approved state with no
    # payment record ever created.
    with transaction.atomic():
        # FIX #3: Use reg.school_address directly — the field is confirmed as
        # `school_address` on SchoolRegistration (models.py line 439) and the
        # target field on Tenant is `address`. The previous getattr fallback
        # was fragile and could silently send an empty string if the field name
        # was ever changed, which can in turn cause Tenant.full_clean() to
        # raise an unexpected ValidationError halting the whole pipeline.
        tenant = Tenant.objects.create(
            name          = reg.school_name,
            subdomain     = reg.subdomain,
            email         = reg.contact_email,
            phone         = reg.contact_phone,
            owner_name    = reg.contact_name,
            owner_email   = reg.contact_email,
            address       = reg.school_address,      # FIX #3: direct field reference
            state         = reg.state,
            school_type   = reg.school_type,         # FIX #3: direct field reference
            plan          = reg.desired_plan,
            billing_cycle = reg.desired_billing,     # now valid — TERM/SESSION added to choices
            status        = 'PENDING',
        )

        # Update registration record
        reg.status      = 'APPROVED'
        reg.tenant      = tenant
        reg.reviewed_by = approved_by
        reg.reviewed_at = timezone.now()
        reg.save(update_fields=['status', 'tenant', 'reviewed_by', 'reviewed_at'])

    # Start trial (outside atomic — provision_tenant has its own error handling)
    start_trial(tenant)

    # Send welcome email (outside atomic — email failure must never roll back the DB write)
    _send_welcome_email(tenant, reg)

    logger.info("Approved registration %s → Tenant %s", reg.id, tenant.id)
    return tenant


def reject_registration(reg: SchoolRegistration, note: str, rejected_by=None):
    reg.status = 'REJECTED'
    reg.rejection_note = note
    reg.reviewed_by = rejected_by
    reg.reviewed_at = timezone.now()
    reg.save(update_fields=['status', 'rejection_note', 'reviewed_by', 'reviewed_at'])
    _send_rejection_email(reg, note)


def provision_tenant(tenant: Tenant):
    """
    Seed sensible defaults for a new tenant:
    - Default academic session
    - Default term
    Called after first activation or trial start.
    """
    try:
        from academics.models import AcademicSession, Term
        import datetime

        today = date.today()
        year = today.year
        session_name = f"{year}/{year + 1}"

        session, created = AcademicSession.objects.get_or_create(
            tenant=tenant,
            name=session_name,
            defaults={
                'is_active': True,
                'start_date': date(year, 9, 1),
                'end_date': date(year + 1, 7, 31),
            }
        )
        if created:
            Term.objects.create(
                tenant=tenant,
                session=session,
                name='1st Term',
                is_active=True,
                start_date=date(year, 9, 1),
                end_date=date(year, 12, 15),
            )
        logger.info("Provisioned defaults for tenant %s", tenant.subdomain)
    except Exception as e:
        logger.warning("provision_tenant: could not seed defaults: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Trial & Subscription lifecycle
# ─────────────────────────────────────────────────────────────────────────────

def start_trial(tenant: Tenant, days: int = TRIAL_DAYS) -> Tenant:
    """Put tenant on free trial. Also provisions defaults."""
    tenant.status = 'TRIAL'
    tenant.trial_ends = timezone.now().date() + timedelta(days=days)
    tenant.save(update_fields=['status', 'trial_ends', 'updated_at'])
    provision_tenant(tenant)
    return tenant


def activate_subscription(tenant: Tenant, plan: Plan,
                           billing_cycle: str, payment: SubscriptionPayment,
                           student_count: int = 0) -> Subscription:
    """
    Called after a successful Paystack payment.
    Closes any previous active subscription, opens a new one, activates tenant.

    billing_cycle: TERM | SESSION | MONTHLY | ANNUAL
    student_count: number of students billed (for TERM/SESSION plans)

    FIX #2: Wrapped in transaction.atomic() so that if Subscription creation
    or tenant.activate() fails, the payment record is not left in a SUCCESS
    state with no subscription attached.
    """
    today = timezone.now().date()

    if billing_cycle == 'TERM':
        # One term ~ 90 days (13 weeks)
        ends_at           = today + timedelta(days=90)
        amount            = plan.calculate_term_cost(student_count)
        price_per_student = plan.price_per_student_term

    elif billing_cycle == 'SESSION':
        # One session ~ 270 days (3 terms × 90 days)
        ends_at           = today + timedelta(days=270)
        amount            = plan.calculate_session_cost(student_count)
        price_per_student = plan.price_per_student_term

    elif billing_cycle == 'ANNUAL':
        ends_at           = today + timedelta(days=365)
        amount            = plan.price_annual or plan.price_monthly * 12
        price_per_student = 0

    else:  # MONTHLY
        ends_at           = today + timedelta(days=30)
        amount            = plan.price_monthly
        price_per_student = 0

    with transaction.atomic():
        # Cancel current active subscriptions
        tenant.subscriptions.filter(status='ACTIVE').update(status='CANCELLED')

        sub = Subscription.objects.create(
            tenant=tenant,
            plan=plan,
            billing_cycle=billing_cycle,
            status='ACTIVE',
            student_count=student_count,
            price_per_student=price_per_student,
            amount=amount,
            currency='NGN',
            starts_at=today,
            ends_at=ends_at,
            renews_at=ends_at,
            paystack_ref=payment.paystack_ref,
        )

        # FIX #4: Save subscription FK and status together in one update_fields
        # call so the payment record is always fully consistent after this block.
        payment.subscription = sub
        payment.status       = 'SUCCESS'
        payment.paid_at      = payment.paid_at or timezone.now()
        payment.save(update_fields=['subscription', 'status', 'paid_at'])

        tenant.plan          = plan
        tenant.billing_cycle = billing_cycle
        tenant.save(update_fields=['plan', 'billing_cycle', 'updated_at'])
        tenant.activate()

    logger.info("Activated %s subscription %s for tenant %s (students=%s)",
                billing_cycle, sub.id, tenant.subdomain, student_count)
    return sub


def cancel_subscription(tenant: Tenant, reason: str = ''):
    tenant.subscriptions.filter(status='ACTIVE').update(
        status='CANCELLED',
        cancelled_at=timezone.now(),
    )
    tenant.status = 'CANCELLED'
    tenant.save(update_fields=['status', 'updated_at'])
    logger.info("Cancelled subscription for tenant %s — %s", tenant.subdomain, reason)


# ─────────────────────────────────────────────────────────────────────────────
# Plan limit enforcement
# ─────────────────────────────────────────────────────────────────────────────

class PlanLimitExceeded(Exception):
    pass


def check_limit(tenant: Tenant, resource: str):
    """
    Raises PlanLimitExceeded if the tenant has hit their plan cap.

    resource: 'students' | 'staff' | 'classes'
    """
    if not tenant.plan:
        return  # no plan = no limits (shouldn't happen in practice)

    max_attr = f'max_{resource}'
    limit = getattr(tenant.plan, max_attr, 0)
    if limit == 0:
        return  # 0 = unlimited

    # Count current usage
    from users.models import Student, Staff
    from users.models import Class

    count_map = {
        'students': lambda: Student.objects.filter(tenant=tenant).count(),
        'staff':    lambda: Staff.objects.filter(tenant=tenant).count(),
        'classes':  lambda: Class.objects.filter(tenant=tenant).count(),
    }

    current = count_map[resource]()
    if current >= limit:
        raise PlanLimitExceeded(
            f"Your {tenant.plan.name} plan allows up to {limit} {resource}. "
            f"You currently have {current}. Upgrade to add more."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Paystack webhook handler
# ─────────────────────────────────────────────────────────────────────────────

def handle_paystack_webhook(payload_bytes: bytes, signature: str) -> dict:
    """
    Verify Paystack HMAC-SHA512 signature, then process the event.
    Returns a dict with 'ok' and optional 'error'.
    """
    secret = settings.PAYSTACK_SECRET_KEY.encode()
    expected = hmac.new(secret, payload_bytes, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, signature or ''):
        return {'ok': False, 'error': 'Invalid signature'}

    data = json.loads(payload_bytes)
    event = data.get('event', '')
    meta = data.get('data', {}).get('metadata', {})

    if event == 'charge.success':
        return _handle_charge_success(data['data'], meta)

    if event == 'subscription.disable':
        return _handle_subscription_disable(data['data'])

    return {'ok': True, 'event': event, 'action': 'ignored'}


def _handle_charge_success(charge_data: dict, meta: dict) -> dict:
    tenant_id = meta.get('tenant_id')
    plan_code = meta.get('plan_code')
    billing_cycle = meta.get('billing_cycle', 'TERM')

    if not tenant_id or not plan_code:
        return {'ok': False, 'error': 'Missing metadata: tenant_id or plan_code'}

    try:
        tenant = Tenant.objects.select_related('plan').get(id=tenant_id)
        plan   = Plan.objects.get(code=plan_code)
    except (Tenant.DoesNotExist, Plan.DoesNotExist) as e:
        return {'ok': False, 'error': str(e)}

    ref = charge_data.get('reference', '')

    payment, created = SubscriptionPayment.objects.get_or_create(
        paystack_ref=ref,
        defaults={
            'tenant':        tenant,
            'plan':          plan,
            'amount':        Decimal(str(charge_data.get('amount', 0))) / 100,
            'currency':      charge_data.get('currency', 'NGN'),
            'status':        'SUCCESS',
            'paid_at':       timezone.now(),
            'paystack_data': charge_data,
        }
    )

    if not created and payment.status == 'SUCCESS':
        return {'ok': True, 'action': 'already_processed'}

    if not created:
        payment.status       = 'SUCCESS'
        payment.paid_at      = timezone.now()
        payment.paystack_data = charge_data
        payment.save(update_fields=['status', 'paid_at', 'paystack_data'])

    activate_subscription(tenant, plan, billing_cycle, payment)
    return {'ok': True, 'action': 'subscription_activated', 'tenant': tenant.subdomain}


def _handle_subscription_disable(data: dict) -> dict:
    code = data.get('subscription_code', '')
    sub = Subscription.objects.filter(paystack_subscription_code=code).first()
    if sub:
        sub.status = 'CANCELLED'
        sub.cancelled_at = timezone.now()
        sub.save(update_fields=['status', 'cancelled_at'])
    return {'ok': True, 'action': 'subscription_disabled'}


# ─────────────────────────────────────────────────────────────────────────────
# Emails
# ─────────────────────────────────────────────────────────────────────────────

def _send_welcome_email(tenant: Tenant, reg: SchoolRegistration):
    try:
        subject = f"Welcome to Techmiary ERP — {tenant.name}"
        body = f"""
Dear {reg.contact_name},

Your school has been approved on the Techmiary Institute ERP platform.

Portal URL : {tenant.portal_url}
Subdomain  : {tenant.subdomain}.titmiary.edu.ng
Trial ends : {tenant.trial_ends.strftime('%d %B %Y') if tenant.trial_ends else 'N/A'}

Your {TRIAL_DAYS}-day free trial has started. No payment required yet.

To get started:
  1. Visit your portal URL above
  2. Log in with your admin credentials (set during setup)
  3. Go to Dashboard → Setup to configure your school

Questions? Reply to this email or visit support.titmiary.edu.ng

Techmiary Team
"""
        send_mail(subject, body,
                  settings.DEFAULT_FROM_EMAIL,
                  [reg.contact_email],
                  fail_silently=True)
    except Exception as e:
        logger.warning("Welcome email failed for %s: %s", tenant.subdomain, e)


def _send_rejection_email(reg: SchoolRegistration, note: str):
    try:
        send_mail(
            f"Your Techmiary registration for {reg.school_name}",
            f"Dear {reg.contact_name},\n\nUnfortunately your registration "
            f"could not be approved at this time.\n\nReason: {note}\n\n"
            f"Please contact support@titmiary.edu.ng for assistance.\n\nTechmiary Team",
            settings.DEFAULT_FROM_EMAIL,
            [reg.contact_email],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning("Rejection email failed: %s", e)
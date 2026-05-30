"""
tenants/school_views.py
Subscription management views for school portals.
Supports per-student billing: TERM and SESSION, plus flat MONTHLY/ANNUAL.
"""
import logging
from decimal import Decimal
import requests
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from tenants.models import Plan, Subscription, SubscriptionPayment
from tenants.services import activate_subscription

logger = logging.getLogger(__name__)


def _require_admin(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:staff_login')
        staff = request.user.staff
        is_admin = (
            request.user.is_superuser or
            (staff is not None and staff.role == 'ADMIN')
        )
        if not is_admin:
            return HttpResponseForbidden("Admin only.")
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── Subscription Status ──────────────────────────────────────────────────────
@_require_admin
def subscription_status(request):
    from users.models import Student
    tenant      = request.tenant
    current_sub = tenant.subscriptions.filter(status='ACTIVE').first()
    plans       = Plan.objects.filter(is_active=True, is_public=True).order_by('sort_order')
    payments    = SubscriptionPayment.objects.filter(tenant=tenant).order_by('-created_at')[:10]
    student_count = Student.objects.count()   # auto-scoped to tenant via TenantManager

    return render(request, 'tenants/school/subscription_status.html', {
        'tenant':              tenant,
        'current_sub':         current_sub,
        'plans':               plans,
        'payments':            payments,
        'student_count':       student_count,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
    })


# ─── Upgrade / Plan Selection ─────────────────────────────────────────────────
@_require_admin
def upgrade_plan(request):
    from users.models import Student
    tenant        = request.tenant
    plans         = Plan.objects.filter(is_active=True, is_public=True).order_by('sort_order')
    student_count = Student.objects.count()   # auto-scoped to tenant

    return render(request, 'tenants/school/upgrade_plan.html', {
        'tenant':              tenant,
        'plans':               plans,
        'student_count':       student_count,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
    })


# ─── AJAX: Calculate price ────────────────────────────────────────────────────
def calculate_price(request):
    """Returns computed price given plan_code + billing_cycle + student_count."""
    plan_code     = request.GET.get('plan_code', '')
    billing_cycle = request.GET.get('billing_cycle', 'TERM')
    try:
        student_count = int(request.GET.get('student_count', 0))
    except ValueError:
        student_count = 0

    plan = Plan.objects.filter(code=plan_code, is_active=True).first()
    if not plan:
        return JsonResponse({'error': 'Plan not found'}, status=404)

    if billing_cycle == 'TERM':
        amount     = float(plan.calculate_term_cost(student_count))
        breakdown  = f"{student_count} students × ₦{plan.price_per_student_term:,.0f} per term"
        period     = "1 Term"
    elif billing_cycle == 'SESSION':
        amount     = float(plan.calculate_session_cost(student_count))
        breakdown  = (f"{student_count} students × ₦{plan.price_per_student_term:,.0f} "
                      f"× {plan.terms_per_session} terms")
        period     = f"1 Session ({plan.terms_per_session} Terms)"
    elif billing_cycle == 'ANNUAL':
        amount     = float(plan.price_annual) if plan.price_annual else float(plan.price_monthly) * 12
        breakdown  = "Flat annual rate"
        period     = "1 Year"
    else:  # MONTHLY
        amount     = float(plan.price_monthly)
        breakdown  = "Flat monthly rate"
        period     = "1 Month"

    return JsonResponse({
        'amount':    amount,
        'formatted': f"₦{amount:,.0f}",
        'breakdown': breakdown,
        'period':    period,
        'plan_name': plan.name,
    })


# ─── Initiate Paystack Payment ────────────────────────────────────────────────
@_require_admin
@require_POST
def initiate_payment(request):
    tenant        = request.tenant
    plan_code     = request.POST.get('plan_code', '')
    billing_cycle = request.POST.get('billing_cycle', 'TERM')
    try:
        student_count = int(request.POST.get('student_count', 0))
    except (ValueError, TypeError):
        student_count = 0

    plan = Plan.objects.filter(code=plan_code, is_active=True).first()
    if not plan:
        messages.error(request, "Invalid plan selected.")
        return redirect('subscription:upgrade')

    # Calculate amount based on billing type
    if billing_cycle == 'TERM':
        amount = plan.calculate_term_cost(student_count)
        period_label = "1 Term"
    elif billing_cycle == 'SESSION':
        amount = plan.calculate_session_cost(student_count)
        period_label = f"1 Session ({plan.terms_per_session} Terms)"
    elif billing_cycle == 'ANNUAL':
        amount = plan.price_annual or plan.price_monthly * 12
        period_label = "1 Year"
    else:
        amount = plan.price_monthly
        period_label = "1 Month"

    if amount <= 0:
        messages.error(request, "Invalid amount calculated. Please contact support.")
        return redirect('subscription:upgrade')

    amount_kobo  = int(Decimal(str(amount)) * 100)
    callback_url = f"{tenant.portal_url}/subscription/callback/"

    payload = {
        "email":        tenant.owner_email or request.user.email,
        "amount":       amount_kobo,
        "currency":     "NGN",
        "callback_url": callback_url,
        "metadata": {
            "tenant_id":     str(tenant.id),
            "plan_code":     plan.code,
            "billing_cycle": billing_cycle,
            "student_count": student_count,
            "period_label":  period_label,
            "custom_fields": [
                {"display_name": "School",        "variable_name": "school",
                 "value": tenant.name},
                {"display_name": "Plan",          "variable_name": "plan",
                 "value": plan.name},
                {"display_name": "Billing",       "variable_name": "billing",
                 "value": f"{billing_cycle} — {period_label}"},
                {"display_name": "Students",      "variable_name": "students",
                 "value": str(student_count)},
            ]
        }
    }

    try:
        resp = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type":  "application/json",
            },
            timeout=15,
        )
        data = resp.json()
        if data.get('status'):
            SubscriptionPayment.objects.create(
                tenant=tenant, plan=plan,
                amount=amount,
                currency='NGN',
                status='PENDING',
                paystack_ref=data['data']['reference'],
            )
            return redirect(data['data']['authorization_url'])
        else:
            error_msg = data.get('message', 'Could not connect to payment gateway.')
    except Exception as e:
        logger.error("Paystack initiate error: %s", e)
        error_msg = 'Payment gateway connection failed. Please try again.'

    return render(request, 'tenants/school/payment_error.html',
                  {'tenant': tenant, 'error': error_msg})


# ─── Payment Callback ─────────────────────────────────────────────────────────
def payment_callback(request):
    tenant = request.tenant
    ref    = request.GET.get('reference', '') or request.GET.get('trxref', '')

    if not ref:
        return redirect('subscription:status')

    payment = SubscriptionPayment.objects.filter(tenant=tenant, paystack_ref=ref).first()
    if payment and payment.status == 'SUCCESS':
        return redirect('subscription:status')

    try:
        resp = requests.get(
            f"https://api.paystack.co/transaction/verify/{ref}",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            timeout=15,
        )
        data = resp.json()
    except Exception as e:
        logger.error("Paystack verify error: %s", e)
        return render(request, 'tenants/school/payment_error.html',
                      {'tenant': tenant, 'error': 'Payment verification failed. Please contact support.'})

    if not data.get('status') or data['data']['status'] != 'success':
        return render(request, 'tenants/school/payment_error.html',
                      {'tenant': tenant,
                       'error': f"Payment not confirmed: {data.get('message', 'Unknown error')}"})

    charge        = data['data']
    meta          = charge.get('metadata', {})
    plan_code     = meta.get('plan_code', '')
    billing_cycle = meta.get('billing_cycle', 'TERM')
    student_count = int(meta.get('student_count', 0))
    plan          = Plan.objects.filter(code=plan_code).first()

    if not plan:
        return render(request, 'tenants/school/payment_error.html',
                      {'tenant': tenant, 'error': 'Plan not found. Please contact support.'})

    if not payment:
        payment = SubscriptionPayment.objects.create(
            tenant=tenant, plan=plan,
            amount=Decimal(str(charge.get('amount', 0))) / 100,
            currency=charge.get('currency', 'NGN'),
            status='PENDING',
            paystack_ref=ref,
        )

    payment.status       = 'SUCCESS'
    payment.paystack_data = charge
    payment.paid_at      = timezone.now()
    payment.save(update_fields=['status', 'paystack_data', 'paid_at'])

    sub = activate_subscription(tenant, plan, billing_cycle, payment,
                                 student_count=student_count)

    return render(request, 'tenants/school/payment_success.html', {
        'tenant':        tenant,
        'plan':          plan,
        'sub':           sub,
        'student_count': student_count,
        'billing_cycle': billing_cycle,
    })


# ─── Invoices ─────────────────────────────────────────────────────────────────
@_require_admin
def invoices(request):
    tenant   = request.tenant
    payments = SubscriptionPayment.objects.filter(tenant=tenant).order_by('-created_at')
    subs     = tenant.subscriptions.order_by('-starts_at')
    return render(request, 'tenants/school/invoices.html', {
        'tenant':   tenant,
        'payments': payments,
        'subs':     subs,
    })
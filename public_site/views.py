"""
public_site/views.py
─────────────────────
Views for the public-facing Techmiary SaaS website.
Served on the root domain: titmiary.edu.ng (or localhost:8000 in dev)

Routes:
  /                → landing page  (if no tenant) OR redirect to school home
  /pricing/        → pricing page
  /register/       → school registration form
  /register/done/  → success page
  /webhook/paystack/ → Paystack event webhook
"""

import json
import logging

logger = logging.getLogger(__name__)

from django.conf import settings
from django.contrib import messages
from django.db import transaction                   # FIX #2: for atomic callback
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from tenants.models import Plan, SchoolRegistration
from tenants.services import handle_paystack_webhook

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Landing page — redirects to school portal if a tenant is on the request
# ─────────────────────────────────────────────────────────────────────────────

def landing(request):
    plans = Plan.objects.filter(is_active=True, is_public=True).order_by('sort_order')
    return render(request, 'public_site/landing.html', {'plans': plans})


# ─────────────────────────────────────────────────────────────────────────────
# Pricing page
# ─────────────────────────────────────────────────────────────────────────────

def pricing(request):
    plans = Plan.objects.filter(is_active=True, is_public=True).order_by('sort_order')
    return render(request, 'public_site/pricing.html', {'plans': plans})


# ─────────────────────────────────────────────────────────────────────────────
# School registration
# ─────────────────────────────────────────────────────────────────────────────

NIGERIAN_STATES = [
    'Abia','Adamawa','Akwa Ibom','Anambra','Bauchi','Bayelsa','Benue',
    'Borno','Cross River','Delta','Ebonyi','Edo','Ekiti','Enugu','FCT',
    'Gombe','Imo','Jigawa','Kaduna','Kano','Katsina','Kebbi','Kogi',
    'Kwara','Lagos','Nasarawa','Niger','Ogun','Ondo','Osun','Oyo',
    'Plateau','Rivers','Sokoto','Taraba','Yobe','Zamfara',
]


def register_school(request):
    plans = Plan.objects.filter(is_active=True, is_public=True).order_by('sort_order')
    selected_plan_code = request.GET.get('plan', '')
    selected_billing   = request.GET.get('billing', 'TERM')

    if request.method == 'POST':
        return _handle_registration(request, plans)

    return render(request, 'public_site/register.html', {
        'plans':              plans,
        'selected_plan_code': selected_plan_code,
        'selected_billing':   selected_billing,
        'states':             NIGERIAN_STATES,
        'school_types': [
            ('nursery',    'Nursery / Primary School'),
            ('secondary',  'Secondary / High School'),
            ('tertiary',   'Tertiary / Polytechnic'),
            ('vocational', 'Vocational / Technical'),
        ],
    })


def _handle_registration(request, plans):
    data = request.POST
    errors = {}

    school_name   = data.get('school_name', '').strip()
    school_type   = data.get('school_type', 'secondary')
    subdomain     = data.get('subdomain', '').strip().lower()
    contact_name  = data.get('contact_name', '').strip()
    contact_email = data.get('contact_email', '').strip().lower()
    contact_phone = data.get('contact_phone', '').strip()
    state         = data.get('state', '').strip()
    school_address = data.get('school_address', '').strip()
    student_count = int(data.get('student_count', 0) or 0)
    plan_code     = data.get('plan_code', '')
    billing_cycle = data.get('desired_billing', 'TERM').strip() or 'TERM'
    if billing_cycle not in ('TERM', 'SESSION', 'MONTHLY', 'ANNUAL'):
        billing_cycle = 'TERM'
    message = data.get('message', '').strip()

    # ── Validate ──────────────────────────────────────────────────────
    if not school_name:
        errors['school_name'] = 'School name is required.'
    if not subdomain:
        errors['subdomain'] = 'Subdomain is required.'
    elif SchoolRegistration.objects.filter(subdomain=subdomain).exists():
        errors['subdomain'] = 'This subdomain is already taken. Try another.'
    if not contact_name:
        errors['contact_name'] = 'Contact name is required.'
    if not contact_email:
        errors['contact_email'] = 'Contact email is required.'
    elif SchoolRegistration.objects.filter(contact_email=contact_email).exists():
        errors['contact_email'] = 'An application with this email already exists.'
    if not contact_phone:
        errors['contact_phone'] = 'Phone number is required.'
    if student_count <= 0:
        errors['student_count'] = 'Please enter your number of students.'

    plan = Plan.objects.filter(code=plan_code, is_active=True).first()
    if not plan:
        errors['plan_code'] = 'Please select a valid plan.'

    def _re_render(extra_errors=None):
        return render(request, 'public_site/register.html', {
            'plans': plans,
            'errors': {**errors, **(extra_errors or {})},
            'form_data': data,
            'states': NIGERIAN_STATES,
            'school_types': [
                ('nursery',    'Nursery / Primary School'),
                ('secondary',  'Secondary / High School'),
                ('tertiary',   'Tertiary / Polytechnic'),
                ('vocational', 'Vocational / Technical'),
            ],
        })

    if errors:
        return _re_render()

    # ── Calculate amount ──────────────────────────────────────────────
    rate = plan.price_per_student_term or 0
    if billing_cycle == 'SESSION':
        terms        = plan.terms_per_session or 3
        amount       = rate * student_count * terms if rate > 0 else plan.price_monthly or 0
        period_label = f"1 Session ({terms} Terms)"
    else:
        amount       = rate * student_count if rate > 0 else plan.price_monthly or 0
        period_label = "1 Term"

    if amount <= 0:
        return _re_render({'plan_code':
            'This plan has no price configured. Please contact support.'})

    amount_kobo = int(float(amount) * 100)

    # ── Build Paystack callback URL ───────────────────────────────────
    root        = getattr(settings, 'ROOT_DOMAIN', 'localhost')
    port        = getattr(settings, 'DEV_PORT', '')
    scheme      = 'http' if root in ('localhost', '127.0.0.1') else 'https'
    port_suffix = f':{port}' if port else ''
    base_url    = f"{scheme}://{root}{port_suffix}"

    # We use subdomain as the identifier in callback since we don't have reg.id yet
    callback_url = f"{base_url}/register/payment-callback/?subdomain={subdomain}"

    paystack_payload = {
        "email":        contact_email,
        "amount":       amount_kobo,
        "currency":     "NGN",
        "callback_url": callback_url,
        "metadata": {
            "school_name":    school_name,
            "subdomain":      subdomain,
            "school_type":    school_type,
            "contact_name":   contact_name,
            "contact_email":  contact_email,
            "contact_phone":  contact_phone,
            "state":          state,
            "school_address": school_address,
            "student_count":  student_count,
            "plan_code":      plan.code,
            "billing_cycle":  billing_cycle,
            "period_label":   period_label,
            "message":        message,
            "custom_fields": [
                {"display_name": "School",   "variable_name": "school",   "value": school_name},
                {"display_name": "Plan",     "variable_name": "plan",     "value": plan.name},
                {"display_name": "Students", "variable_name": "students", "value": str(student_count)},
                {"display_name": "Period",   "variable_name": "period",   "value": period_label},
            ]
        }
    }

    try:
        import requests as req_lib
        logger.info(
            "Initiating Paystack: school=%s plan=%s billing=%s students=%s amount=₦%s",
            school_name, plan.code, billing_cycle, student_count, amount
        )

        init_resp = req_lib.post(
            "https://api.paystack.co/transaction/initialize",
            json=paystack_payload,
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type":  "application/json",
            },
            timeout=15,
        )
        init_data = init_resp.json()

        if not init_data.get('status'):
            logger.error("Paystack init failed: %s", init_data)
            return _re_render({'global_error':
                f"Payment gateway error: {init_data.get('message', 'Please try again.')} "
                f"Your school has NOT been registered."})

        # ── Step 2: Payment init succeeded — NOW save registration ────
        paystack_redirect_url = init_data['data']['authorization_url']

        reg = SchoolRegistration.objects.create(
            school_name    = school_name,
            school_type    = school_type,
            subdomain      = subdomain,
            contact_name   = contact_name,
            contact_email  = contact_email,
            contact_phone  = contact_phone,
            school_address = school_address,   # FIX #3: pass address through correctly
            state          = state,
            student_count  = student_count,
            desired_plan   = plan,
            desired_billing= billing_cycle,
            message        = message,
        )

        _notify_team_new_registration(reg)
        logger.info("Registration %s saved. Redirecting to Paystack.", reg.id)
        return redirect(paystack_redirect_url)

    except Exception as e:
        logger.error("Paystack/registration error: %s", e)
        return _re_render({'global_error':
            'Could not connect to payment gateway. '
            'Your school has NOT been registered. Please check your internet and try again.'})


def register_done(request):
    return render(request, 'public_site/register_done.html')


def registration_payment_callback(request):
    """
    Paystack redirects here after the school pays during registration.

    Flow:
      1. Verify payment with Paystack API
      2. Guard against duplicate callback (Paystack can call twice)
      3. Auto-approve the SchoolRegistration  ─┐ wrapped in
      4. Create SubscriptionPayment record     ─┤ transaction.atomic()
      5. Create Subscription, activate tenant ─┘
      6. Render success page
    """
    from decimal import Decimal
    from tenants.models import SchoolRegistration as SR, Plan, SubscriptionPayment
    from tenants.services import approve_registration, activate_subscription

    reg_id    = request.GET.get('reg', '')
    subdomain = request.GET.get('subdomain', '')
    ref       = request.GET.get('reference', '') or request.GET.get('trxref', '')

    if not ref:
        return redirect('public_site:register_done')

    # ── Step 1: Verify with Paystack ──────────────────────────────────
    try:
        import requests as req_lib
        resp = req_lib.get(
            f"https://api.paystack.co/transaction/verify/{ref}",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            timeout=15,
        )
        result = resp.json()
    except Exception as e:
        logger.error("Paystack verify error (registration): %s", e)
        return render(request, 'public_site/register_payment_failed.html',
                      {'error': 'Payment verification failed. Please contact support.'})

    if not result.get('status') or result['data']['status'] != 'success':
        return render(request, 'public_site/register_payment_failed.html',
                      {'error': result.get('message', 'Payment not confirmed by Paystack.')})

    charge        = result['data']
    meta          = charge.get('metadata', {})
    amount        = Decimal(str(charge.get('amount', 0))) / 100
    plan_code     = meta.get('plan_code', '')
    billing_cycle = meta.get('billing_cycle', 'TERM')
    student_count = int(meta.get('student_count', 0))
    school_name   = meta.get('school_name', '')
    period_label  = meta.get('period_label', '')
    subdomain     = meta.get('subdomain', '') or subdomain

    # ── Step 2: Resolve plan and registration ─────────────────────────
    plan = Plan.objects.filter(code=plan_code).first()

    # Find registration — subdomain is the most reliable identifier
    reg = None
    if subdomain:
        reg = SR.objects.filter(subdomain=subdomain).order_by('-created_at').first()
    if not reg and reg_id:
        reg = SR.objects.filter(id=reg_id).first()

    # ── Step 3: Guard against duplicate callback ──────────────────────
    # Paystack can redirect the user to the callback URL more than once.
    # FIX #4: Check for an existing SUCCESS payment and short-circuit
    # immediately — before any DB writes — to avoid race conditions.
    existing = SubscriptionPayment.objects.filter(paystack_ref=ref, status='SUCCESS').first()
    if existing:
        logger.info("Duplicate callback for ref %s — already processed.", ref)
        return render(request, 'public_site/register_payment_success.html', {
            'reg':           reg,
            'amount':        amount,
            'ref':           ref,
            'plan_name':     plan.name if plan else plan_code,
            'period_label':  period_label,
            'student_count': student_count,
            'school_name':   school_name or (reg.school_name if reg else ''),
            'tenant':        existing.tenant,
            'already_done':  True,
        })

    # ── Steps 4–6: Approve → record payment → activate (all atomic) ──
    # FIX #2: The entire pipeline runs inside a single atomic transaction.
    # If any step raises an exception, ALL database writes are rolled back,
    # leaving no orphaned Tenant, payment, or subscription records.
    tenant  = None
    payment = None
    sub     = None

    if plan:
        try:
            with transaction.atomic():
                # 4a. Approve registration and create Tenant
                if reg and reg.status == 'PENDING':
                    tenant = approve_registration(reg, approved_by=None)
                    logger.info("Auto-approved registration %s → tenant %s",
                                reg.id, tenant.subdomain)
                elif reg and reg.tenant:
                    tenant = reg.tenant
                    logger.info("Registration already approved, tenant: %s", tenant)
                else:
                    logger.error("No reg found: reg_id=%s subdomain=%s meta=%s",
                                 reg_id, subdomain, meta)

                if not tenant:
                    raise ValueError(
                        f"Cannot complete payment: no tenant resolved for subdomain={subdomain}"
                    )

                # 4b. FIX #4: Create the SubscriptionPayment record cleanly.
                # Use get_or_create to handle the edge case where a PENDING
                # record was already written, then update only if not freshly
                # created — never blindly overwrite a stale object.
                payment, created = SubscriptionPayment.objects.get_or_create(
                    paystack_ref=ref,
                    defaults={
                        'tenant':        tenant,
                        'plan':          plan,
                        'amount':        amount,
                        'currency':      charge.get('currency', 'NGN'),
                        'status':        'PENDING',   # activate_subscription will set SUCCESS
                        'paystack_data': charge,
                    }
                )
                if not created:
                    # Record already exists (e.g. from a prior PENDING attempt);
                    # update the fields that may have been stale.
                    payment.tenant       = tenant
                    payment.plan         = plan
                    payment.amount       = amount
                    payment.paystack_data = charge
                    payment.save(update_fields=['tenant', 'plan', 'amount', 'paystack_data'])

                # 4c. Create Subscription and activate tenant.
                # activate_subscription also sets payment.status = 'SUCCESS'
                # and links payment.subscription — all inside its own atomic
                # block, which nests safely here.
                sub = activate_subscription(
                    tenant, plan, billing_cycle, payment,
                    student_count=student_count
                )
                logger.info(
                    "Subscription created: tenant=%s plan=%s billing=%s "
                    "students=%s amount=%s ends=%s",
                    tenant.subdomain, plan.code, billing_cycle,
                    student_count, amount, sub.ends_at
                )

        except Exception as e:
            logger.error(
                "Payment pipeline failed for ref=%s subdomain=%s: %s",
                ref, subdomain, e, exc_info=True
            )
            return render(request, 'public_site/register_payment_failed.html', {
                'error': (
                    'Your payment was received by Paystack but we encountered an error '
                    'activating your account. Please contact support with reference: '
                    f'{ref}'
                )
            })
    else:
        logger.error(
            "Could not resolve plan for plan_code=%s — payment ref=%s",
            plan_code, ref
        )

    return render(request, 'public_site/register_payment_success.html', {
        'reg':           reg,
        'amount':        amount,
        'ref':           ref,
        'plan_name':     plan.name if plan else plan_code,
        'period_label':  period_label,
        'student_count': student_count,
        'school_name':   school_name or (reg.school_name if reg else ''),
        'tenant':        tenant,
        'sub':           sub,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Paystack webhook
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def paystack_webhook(request):
    payload  = request.body
    sig      = request.headers.get('X-Paystack-Signature', '')
    result   = handle_paystack_webhook(payload, sig)

    if not result.get('ok'):
        logger.warning("Paystack webhook rejected: %s", result.get('error'))
        return HttpResponse(status=400)

    return HttpResponse(status=200)


# ─────────────────────────────────────────────────────────────────────────────
# Subdomain availability checker (AJAX)
# ─────────────────────────────────────────────────────────────────────────────

def check_subdomain(request):
    subdomain = request.GET.get('subdomain', '').strip().lower()
    if not subdomain:
        return JsonResponse({'available': False, 'message': 'Enter a subdomain.'})

    from tenants.models import RESERVED_SLUGS, _slug_validator
    from django.core.exceptions import ValidationError

    try:
        _slug_validator(subdomain)
    except ValidationError as e:
        return JsonResponse({'available': False, 'message': str(e.message)})

    if subdomain in RESERVED_SLUGS:
        return JsonResponse({'available': False, 'message': 'This subdomain is reserved.'})

    taken = (SchoolRegistration.objects.filter(subdomain=subdomain).exists() or
             __import__('tenants.models', fromlist=['Tenant']).Tenant.objects
             .filter(subdomain=subdomain).exists())

    if taken:
        return JsonResponse({'available': False,
                             'message': f'"{subdomain}" is already taken.'})

    return JsonResponse({'available': True,
                         'message': f'"{subdomain}.titmiary.edu.ng" is available!'})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _notify_team_new_registration(reg: SchoolRegistration):
    from django.core.mail import send_mail
    try:
        send_mail(
            subject=f"New School Registration: {reg.school_name}",
            message=(
                f"School: {reg.school_name}\n"
                f"Subdomain: {reg.subdomain}\n"
                f"Contact: {reg.contact_name} <{reg.contact_email}>\n"
                f"Phone: {reg.contact_phone}\n"
                f"State: {reg.state}\n"
                f"Students: {reg.student_count}\n"
                f"Desired Plan: {reg.desired_plan}\n"
                f"Message: {reg.message}\n\n"
                f"Review at: http://localhost:8000/admin/tenants/schoolregistration/"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning("Team notification email failed: %s", e)
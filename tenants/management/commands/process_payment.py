"""
Save as: tenants/management/commands/process_payment.py
Run as:  python manage.py process_payment --ref YOUR_PAYSTACK_REF

Find the reference in your Paystack dashboard → Transactions
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Manually process a Paystack payment reference and create all DB records'

    def add_arguments(self, parser):
        parser.add_argument('--ref', required=True, help='Paystack transaction reference')
        parser.add_argument('--subdomain', default='', help='School subdomain (optional)')

    def handle(self, *args, **options):
        import requests
        from decimal import Decimal
        from django.conf import settings
        from django.utils import timezone
        from tenants.models import Plan, SubscriptionPayment, SchoolRegistration, Tenant
        from tenants.services import approve_registration, activate_subscription

        ref       = options['ref']
        subdomain = options.get('subdomain', '')

        self.stdout.write(f"\n🔍 Verifying payment: {ref}")

        # Step 1: Verify with Paystack
        try:
            resp = requests.get(
                f"https://api.paystack.co/transaction/verify/{ref}",
                headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
                timeout=15,
            )
            result = resp.json()
        except Exception as e:
            self.stderr.write(f"❌ Network error: {e}")
            return

        if not result.get('status') or result['data']['status'] != 'success':
            self.stderr.write(f"❌ Payment not confirmed: {result.get('message')}")
            self.stderr.write(str(result))
            return

        charge        = result['data']
        meta          = charge.get('metadata', {})
        amount        = Decimal(str(charge['amount'])) / 100
        plan_code     = meta.get('plan_code', '')
        billing_cycle = meta.get('billing_cycle', 'TERM')
        student_count = int(meta.get('student_count', 0))
        school_name   = meta.get('school_name', '')
        period_label  = meta.get('period_label', '')
        meta_subdomain= meta.get('subdomain', subdomain)

        self.stdout.write(self.style.SUCCESS(f"✅ Payment verified: ₦{amount:,.0f}"))
        self.stdout.write(f"   School:    {school_name}")
        self.stdout.write(f"   Plan:      {plan_code}")
        self.stdout.write(f"   Billing:   {billing_cycle}")
        self.stdout.write(f"   Students:  {student_count}")
        self.stdout.write(f"   Subdomain: {meta_subdomain}")

        # Step 2: Get plan
        plan = Plan.objects.filter(code=plan_code).first()
        if not plan:
            self.stderr.write(f"❌ Plan not found: {plan_code}")
            self.stderr.write(f"   Available plans: {list(Plan.objects.values_list('code', flat=True))}")
            return
        self.stdout.write(f"   Plan obj:  {plan.name}")

        # Step 3: Find registration
        reg = None
        if meta_subdomain:
            reg = SchoolRegistration.objects.filter(
                subdomain=meta_subdomain
            ).order_by('-created_at').first()
        self.stdout.write(f"   Reg:       {reg} (status: {reg.status if reg else 'N/A'})")

        # Step 4: Approve registration / get tenant
        tenant = None
        if reg and reg.status == 'PENDING':
            try:
                tenant = approve_registration(reg, approved_by=None)
                self.stdout.write(self.style.SUCCESS(f"✅ Registration approved → Tenant: {tenant.name}"))
            except Exception as e:
                self.stderr.write(f"❌ approve_registration failed: {e}")
                import traceback; traceback.print_exc()
                return
        elif reg and reg.tenant:
            tenant = reg.tenant
            self.stdout.write(f"   Already approved → Tenant: {tenant.name}")
        elif reg and reg.status == 'APPROVED' and not reg.tenant:
            self.stderr.write("❌ Reg is APPROVED but has no tenant linked — data inconsistency")
            return
        else:
            self.stderr.write(f"❌ No registration found for subdomain '{meta_subdomain}'")
            self.stderr.write("   Registrations in DB:")
            for r in SchoolRegistration.objects.all():
                self.stderr.write(f"   - {r.subdomain} ({r.status})")
            return

        # Step 5: Create SubscriptionPayment
        try:
            payment, created = SubscriptionPayment.objects.get_or_create(
                paystack_ref=ref,
                defaults={
                    'tenant':       tenant,
                    'plan':         plan,
                    'amount':       amount,
                    'currency':     charge.get('currency', 'NGN'),
                    'status':       'SUCCESS',
                    'paid_at':      timezone.now(),
                    'paystack_data': charge,
                }
            )
            if not created:
                payment.status = 'SUCCESS'
                payment.paid_at = timezone.now()
                payment.paystack_data = charge
                payment.save(update_fields=['status', 'paid_at', 'paystack_data'])

            self.stdout.write(self.style.SUCCESS(
                f"✅ SubscriptionPayment {'created' if created else 'updated'}: {payment.id}"
            ))
        except Exception as e:
            self.stderr.write(f"❌ SubscriptionPayment creation failed: {e}")
            import traceback; traceback.print_exc()
            return

        # Step 6: Create Subscription
        try:
            sub = activate_subscription(
                tenant, plan, billing_cycle, payment,
                student_count=student_count
            )
            self.stdout.write(self.style.SUCCESS(
                f"✅ Subscription created: {sub.id} — active until {sub.ends_at}"
            ))
        except Exception as e:
            self.stderr.write(f"❌ activate_subscription failed: {e}")
            import traceback; traceback.print_exc()
            return

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(f"✅ ALL DONE! {tenant.name} is now ACTIVE"))
        self.stdout.write(f"   Portal:    {tenant.portal_url}")
        self.stdout.write(f"   Status:    {tenant.status}")
        self.stdout.write(f"   Plan:      {tenant.plan.name}")
        self.stdout.write(f"   Expires:   {sub.ends_at}")
        self.stdout.write("=" * 60)
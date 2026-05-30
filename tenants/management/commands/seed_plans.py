"""python manage.py seed_plans"""
from django.core.management.base import BaseCommand
from tenants.models import Plan

PLANS = [
    {
        'name': 'Starter', 'code': 'starter', 'sort_order': 1,
        'description': 'Perfect for small schools. Core academics, CBT and results.',
        'price_per_student_term': 2000,
        'terms_per_session': 3,
        'price_monthly': 0, 'price_annual': 0,
        'max_students': 200, 'max_staff': 15, 'max_classes': 8,
        'feature_academics': True,  'feature_cbt': True,
        'feature_results': True,    'feature_finance': False,
        'feature_payroll': False,   'feature_hostel': False,
        'feature_communications': False, 'feature_inventory': False,
        'feature_timetable': True,  'feature_announcements': True,
        'feature_parent_portal': False, 'feature_api_access': False,
        'feature_custom_domain': False,
        'highlight_label': '', 'highlight_color': '',
        'is_active': True, 'is_public': True,
    },
    {
        'name': 'Growth', 'code': 'growth', 'sort_order': 2,
        'description': 'Finance, communications, parent portal. Built for growing schools.',
        'price_per_student_term': 3000,
        'terms_per_session': 3,
        'price_monthly': 0, 'price_annual': 0,
        'max_students': 600, 'max_staff': 40, 'max_classes': 25,
        'feature_academics': True,  'feature_cbt': True,
        'feature_results': True,    'feature_finance': True,
        'feature_payroll': True,    'feature_hostel': False,
        'feature_communications': True, 'feature_inventory': False,
        'feature_timetable': True,  'feature_announcements': True,
        'feature_parent_portal': True, 'feature_api_access': False,
        'feature_custom_domain': False,
        'highlight_label': 'Most Popular', 'highlight_color': '#e8b84b',
        'is_active': True, 'is_public': True,
    },
    {
        'name': 'Premium', 'code': 'premium', 'sort_order': 3,
        'description': 'Full suite — hostel, inventory, payroll, custom domain and more.',
        'price_per_student_term': 5000,
        'terms_per_session': 3,
        'price_monthly': 0, 'price_annual': 0,
        'max_students': 0, 'max_staff': 0, 'max_classes': 0,
        'feature_academics': True,  'feature_cbt': True,
        'feature_results': True,    'feature_finance': True,
        'feature_payroll': True,    'feature_hostel': True,
        'feature_communications': True, 'feature_inventory': True,
        'feature_timetable': True,  'feature_announcements': True,
        'feature_parent_portal': True, 'feature_api_access': True,
        'feature_custom_domain': True,
        'highlight_label': '', 'highlight_color': '',
        'is_active': True, 'is_public': True,
    },
]

class Command(BaseCommand):
    help = 'Seed subscription plans with per-student pricing'

    def handle(self, *args, **options):
        for data in PLANS:
            code = data.pop('code')
            obj, created = Plan.objects.update_or_create(code=code, defaults=data)
            data['code'] = code
            action = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(
                f"  {action}: {obj.name} — ₦{obj.price_per_student_term:,.0f}/student/term  "
                f"(₦{obj.price_per_student_session:,.0f}/student/session)"
            ))
        self.stdout.write(self.style.SUCCESS('\nPlans seeded successfully.'))
        self.stdout.write("\nPricing summary:")
        self.stdout.write(f"  {'Plan':<12} {'Per Student/Term':>18} {'Per Student/Session':>22} {'Students':>10}")
        self.stdout.write("  " + "-"*65)
        for p in Plan.objects.filter(is_active=True).order_by('sort_order'):
            students = str(p.max_students) if p.max_students else 'Unlimited'
            self.stdout.write(
                f"  {p.name:<12} {'₦'+str(int(p.price_per_student_term))+'/student':>18} "
                f"{'₦'+str(int(p.price_per_student_session))+'/student':>22} {students:>10}"
            )
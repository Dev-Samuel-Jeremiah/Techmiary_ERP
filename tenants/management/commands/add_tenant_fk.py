"""
tenants/management/commands/add_tenant_fk.py
─────────────────────────────────────────────
Management command that generates a single squashed migration
adding `tenant` FK to every multi-tenant model.

Run once after merging this SaaS branch:
  python manage.py add_tenant_fk

This is informational / a helper. In practice you manually create or
auto-generate the migrations per-app with makemigrations after editing
each model to include TenantModelMixin.
"""

from django.core.management.base import BaseCommand


TENANT_FK_MODELS = {
    # app_label: [ModelName, ...]
    'users':         ['Staff', 'Student', 'Class', 'Subject', 'ClassSubject',
                      'StudentSubject', 'StaffSubjectClass', 'Attendance',
                      'StudentPromotionRecord'],
    'academics':     ['AcademicSession', 'Term', 'PublicHoliday'],
    'results':       ['TermResult', 'Score'],
    'cbt':           ['Exam', 'Question', 'StudentExamSession'],
    'finance':       ['Wallet', 'Transaction', 'FeeStructure', 'FeePayment',
                      'Payment', 'TopUpRequest'],
    'payroll':       ['PayrollRecord'],
    'hostel':        ['HostelBuilding', 'HostelFloor', 'HostelRoom',
                      'Bed', 'BoarderProfile'],
    'communications':['Campaign', 'MessageLog', 'MessageTemplate'],
    'inventory':     ['Asset', 'StockMovement'],
    'timetable':     ['TimetableConfig', 'TimeSlot'],
    'announcement':  ['Announcement'],
    'classroom':     ['ClassRoom'],
}


class Command(BaseCommand):
    help = 'Print the list of models that need a tenant FK added'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            '\n=== Models requiring tenant FK ===\n'))
        for app, models in TENANT_FK_MODELS.items():
            self.stdout.write(f'\n{self.style.WARNING(app)}:')
            for m in models:
                self.stdout.write(f'  • {m}')

        self.stdout.write(self.style.SUCCESS(
            '\n\nFor each model above:\n'
            '  1. Add `from tenants.managers import TenantModelMixin` to the app models.py\n'
            '  2. Make the model inherit TenantModelMixin (as the first base after models.Model)\n'
            '  3. Run: python manage.py makemigrations <app_label>\n'
            '  4. Run: python manage.py migrate\n'
        ))

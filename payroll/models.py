"""payroll/models.py — Staff payroll tracking"""
from decimal import Decimal
from django.conf import settings
from django.db import models
from tenants.managers import TenantModelMixin, TenantManager

from django.utils import timezone
from users.models import Staff


class SalaryGrade(TenantModelMixin, models.Model):
    """Grade level with base salary — e.g. Grade 8 = ₦80,000/month"""
    name         = models.CharField(max_length=50, unique=True)
    base_salary  = models.DecimalField(max_digits=14, decimal_places=2)
    description  = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name}  ₦{self.base_salary:,.2f}/mo"


class StaffPayroll(TenantModelMixin, models.Model):
    """Links a Staff member to their salary grade and bank details."""
    staff        = models.OneToOneField(Staff, on_delete=models.CASCADE,
                                        related_name='payroll')
    grade        = models.ForeignKey(SalaryGrade, on_delete=models.PROTECT,
                                     null=True, blank=True)
    basic_salary = models.DecimalField(max_digits=14, decimal_places=2,
                                       default=Decimal('0.00'))
    bank_name    = models.CharField(max_length=100, blank=True)
    account_no   = models.CharField(max_length=20, blank=True)
    account_name = models.CharField(max_length=200, blank=True)
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payroll — {self.staff.full_name}  ₦{self.basic_salary:,.2f}"


class SalaryPayment(TenantModelMixin, models.Model):
    """A monthly salary disbursement record."""
    STATUS_CHOICES = [
        ('PENDING',  'Pending'),
        ('PAID',     'Paid'),
        ('REVERSED', 'Reversed'),
    ]
    METHOD_CHOICES = [
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CASH',          'Cash'),
        ('CHEQUE',        'Cheque'),
    ]

    staff_payroll  = models.ForeignKey(StaffPayroll, on_delete=models.PROTECT,
                                       related_name='payments')
    month          = models.PositiveIntegerField()  # 1–12
    year           = models.PositiveIntegerField()
    gross_salary   = models.DecimalField(max_digits=14, decimal_places=2)
    deductions     = models.DecimalField(max_digits=14, decimal_places=2,
                                         default=Decimal('0.00'))
    net_salary     = models.DecimalField(max_digits=14, decimal_places=2)
    method         = models.CharField(max_length=20, choices=METHOD_CHOICES,
                                      default='BANK_TRANSFER')
    reference      = models.CharField(max_length=80, blank=True)
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                      default='PENDING')
    note           = models.TextField(blank=True)
    paid_by        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                       on_delete=models.SET_NULL,
                                       null=True, blank=True)
    paid_at        = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-month']
        unique_together = ('staff_payroll', 'month', 'year')

    @property
    def month_name(self):
        import calendar
        return calendar.month_name[self.month]

    def __str__(self):
        return (f"{self.staff_payroll.staff.full_name}  "
                f"{self.month_name} {self.year}  ₦{self.net_salary:,.2f}")
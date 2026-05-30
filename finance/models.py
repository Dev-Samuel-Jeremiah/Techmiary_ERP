"""
finance/models.py  —  TIT Finance ERP
Full production models: Wallet, Transaction, FeeStructure, SchoolItem,
Invoice, Payment, ParentBilling, ChildBilling, ChildPaymentAllocation,
Installment, FeePayment, Purchase, TopUpRequest, AuditLog
"""

from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models
from tenants.managers import TenantModelMixin, TenantManager
from django.db import models, transaction as db_transaction
from django.utils import timezone

from users.models import Student
from academics.models import AcademicSession, Term


def _gen_ref(prefix="TIT"):
    return prefix + uuid.uuid4().hex[:10].upper()


# ── Wallet ────────────────────────────────────────────────────────────────────
class Wallet(TenantModelMixin, models.Model):
    student    = models.OneToOneField(Student, on_delete=models.CASCADE,
                                      related_name='wallet')
    balance    = models.DecimalField(max_digits=14, decimal_places=2,
                                     default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Parent Wallet"

    def __str__(self):
        return f"Wallet – {self.student.full_name}  ₦{self.balance:,.2f}"

    def credit(self, amount, description, ref=None, performed_by=None,
               category='TOPUP', related_payment=None):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Credit amount must be positive.")
        with db_transaction.atomic():
            self.balance += amount
            self.save(update_fields=['balance', 'updated_at'])
            return Transaction.objects.create(
                wallet=self, txn_type=Transaction.CREDIT, amount=amount,
                description=description, reference=ref or _gen_ref("CRD"),
                category=category, performed_by=performed_by,
                balance_after=self.balance, related_payment=related_payment,
            )

    def debit(self, amount, description, ref=None, performed_by=None,
              category='FEE', related_payment=None):
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Debit amount must be positive.")
        if self.balance < amount:
            raise ValueError(
                f"Insufficient balance. Available: ₦{self.balance:,.2f}, Required: ₦{amount:,.2f}")
        with db_transaction.atomic():
            self.balance -= amount
            self.save(update_fields=['balance', 'updated_at'])
            return Transaction.objects.create(
                wallet=self, txn_type=Transaction.DEBIT, amount=amount,
                description=description, reference=ref or _gen_ref("DBT"),
                category=category, performed_by=performed_by,
                balance_after=self.balance, related_payment=related_payment,
            )

    @classmethod
    def get_or_create_for_student(cls, student):
        wallet, _ = cls.objects.get_or_create(student=student)
        return wallet

    @staticmethod
    def _gen_ref():
        return _gen_ref("TIT")


# ── Transaction ───────────────────────────────────────────────────────────────
class Transaction(TenantModelMixin, models.Model):
    CREDIT = 'CREDIT'
    DEBIT  = 'DEBIT'
    TYPE_CHOICES = [(CREDIT, 'Credit'), (DEBIT, 'Debit')]
    CATEGORY_CHOICES = [
        ('TOPUP','Wallet Top-Up'),('FEE','School Fee'),
        ('TEXTBOOK','Textbook'),('UNIFORM','Uniform'),
        ('SUPPLY','School Supply'),('PAYSTACK','Paystack Payment'),
        ('REFUND','Refund'),('REVERSAL','Reversal'),
        ('SALARY','Salary'),('OTHER','Other'),
    ]
    STATUS_CHOICES = [
        ('PENDING','Pending'),('COMPLETED','Completed'),
        ('FAILED','Failed'),('REVERSED','Reversed'),
    ]

    wallet          = models.ForeignKey(Wallet, on_delete=models.PROTECT,
                                        related_name='transactions')
    txn_type        = models.CharField(max_length=6, choices=TYPE_CHOICES)
    category        = models.CharField(max_length=20, choices=CATEGORY_CHOICES,
                                       default='OTHER')
    amount          = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after   = models.DecimalField(max_digits=14, decimal_places=2)
    description     = models.CharField(max_length=300)
    reference       = models.CharField(max_length=80, unique=True)
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                       default='COMPLETED')
    performed_by    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                        on_delete=models.SET_NULL,
                                        null=True, blank=True,
                                        related_name='finance_transactions')
    related_payment = models.ForeignKey('Payment', on_delete=models.SET_NULL,
                                        null=True, blank=True,
                                        related_name='linked_transactions')
    note            = models.TextField(blank=True)
    created_at      = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.txn_type} ₦{self.amount:,.2f}  {self.reference}"


# ── Fee Structure ─────────────────────────────────────────────────────────────
class FeeStructure(TenantModelMixin, models.Model):
    name         = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    amount       = models.DecimalField(max_digits=14, decimal_places=2)
    category     = models.CharField(max_length=20,
                                    choices=Transaction.CATEGORY_CHOICES,
                                    default='FEE')
    term         = models.ForeignKey(Term, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name='fee_structures')
    school_class = models.ForeignKey('users.Class', on_delete=models.SET_NULL,
                                     null=True, blank=True)
    session      = models.ForeignKey(AcademicSession, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    is_active    = models.BooleanField(default=True)
    is_compulsory = models.BooleanField(default=False)
    due_date     = models.DateField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name}  ₦{self.amount:,.2f}"


# ── School Item ───────────────────────────────────────────────────────────────
class SchoolItem(TenantModelMixin, models.Model):
    TYPE_CHOICES = [
        ('TEXTBOOK','Textbook'),('UNIFORM','Uniform'),
        ('SUPPLY','School Supply'),('OTHER','Other'),
    ]
    name            = models.CharField(max_length=200)
    description     = models.TextField(blank=True)
    item_type       = models.CharField(max_length=10, choices=TYPE_CHOICES)
    price           = models.DecimalField(max_digits=14, decimal_places=2)
    stock_qty       = models.PositiveIntegerField(default=0)
    school_class     = models.ForeignKey('users.Class', on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         help_text='Leave blank = available to all classes')
    assigned_student = models.ForeignKey('users.Student', on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name='assigned_items',
                                         help_text='Assign this item to ONE specific student only')
    image            = models.ImageField(upload_to='school_items/', blank=True, null=True)
    is_active        = models.BooleanField(default=True)
    inventory_asset  = models.ForeignKey('inventory.Asset', on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name='school_items')
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['item_type', 'name']

    def __str__(self):
        return f"{self.name}  ₦{self.price:,.2f}"


# ── Invoice ───────────────────────────────────────────────────────────────────
class Invoice(TenantModelMixin, models.Model):
    STATUS_CHOICES = [
        ('DRAFT','Draft'),('SENT','Sent'),('PARTIAL','Partially Paid'),
        ('PAID','Fully Paid'),('CANCELLED','Cancelled'),('OVERDUE','Overdue'),
    ]
    student      = models.ForeignKey(Student, on_delete=models.PROTECT,
                                     related_name='invoices')
    session      = models.ForeignKey(AcademicSession, on_delete=models.PROTECT,
                                     null=True, blank=True)
    term         = models.ForeignKey(Term, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    invoice_no   = models.CharField(max_length=30, unique=True)
    title        = models.CharField(max_length=200, default='School Fee Invoice')
    total        = models.DecimalField(max_digits=14, decimal_places=2,
                                       default=Decimal('0.00'))
    amount_paid  = models.DecimalField(max_digits=14, decimal_places=2,
                                       default=Decimal('0.00'))
    balance_due  = models.DecimalField(max_digits=14, decimal_places=2,
                                       default=Decimal('0.00'))
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                    default='DRAFT')
    due_date     = models.DateField(null=True, blank=True)
    note         = models.TextField(blank=True)
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.SET_NULL,
                                     null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.invoice_no}  {self.student.full_name}"

    def recalculate(self):
        self.total      = sum(i.amount for i in self.items.all())
        self.balance_due = max(Decimal('0'), self.total - self.amount_paid)
        if self.balance_due == 0 and self.total > 0:
            self.status = 'PAID'
        elif self.amount_paid > 0:
            self.status = 'PARTIAL'
        self.save(update_fields=['total','balance_due','status','updated_at'])

    @classmethod
    def generate_for_student(cls, student, term, session, created_by=None):
        from django.db.models import Q
        fees = FeeStructure.objects.filter(is_active=True).filter(
            Q(school_class=student.class_assigned) | Q(school_class__isnull=True)
        ).filter(
            Q(term=term) | Q(term__isnull=True)
        ).filter(
            Q(session=session) | Q(session__isnull=True)
        )
        inv = cls.objects.create(
            student=student, session=session, term=term,
            invoice_no=_gen_ref("INV"),
            title=f"Fee Invoice — {term} / {session}",
            due_date=getattr(term, 'closing_date', None),
            created_by=created_by,
        )
        for fee in fees:
            InvoiceItem.objects.create(
                invoice=inv, description=fee.name,
                amount=fee.amount, fee_structure=fee, student=student,
            )
        inv.recalculate()
        return inv


class InvoiceItem(TenantModelMixin, models.Model):
    invoice       = models.ForeignKey(Invoice, on_delete=models.CASCADE,
                                      related_name='items')
    description   = models.CharField(max_length=300)
    amount        = models.DecimalField(max_digits=14, decimal_places=2)
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    school_item   = models.ForeignKey(SchoolItem, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    student       = models.ForeignKey(Student, on_delete=models.SET_NULL,
                                      null=True, blank=True)

    def __str__(self):
        return f"{self.description}  ₦{self.amount:,.2f}"


# ── Payment ───────────────────────────────────────────────────────────────────
class Payment(TenantModelMixin, models.Model):
    PENDING = 'PENDING'; APPROVED = 'APPROVED'; REJECTED = 'REJECTED'
    STATUS_CHOICES = [
        (PENDING,'Pending'),(APPROVED,'Approved'),(REJECTED,'Rejected'),
    ]
    METHOD_CHOICES = [
        ('CASH','Cash'),('BANK_TRANSFER','Bank Transfer'),
        ('PAYSTACK','Paystack (Online)'),('POS','POS / Card'),('CHEQUE','Cheque'),
    ]

    wallet         = models.ForeignKey(Wallet, on_delete=models.PROTECT,
                                       related_name='payments')
    invoice        = models.ForeignKey(Invoice, on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name='payments')
    amount         = models.DecimalField(max_digits=14, decimal_places=2)
    reference      = models.CharField(max_length=100, unique=True)
    method         = models.CharField(max_length=20, choices=METHOD_CHOICES,
                                      default='CASH')
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                      default=PENDING)
    proof          = models.ImageField(upload_to='payment_proofs/', blank=True, null=True)
    paystack_ref   = models.CharField(max_length=100, blank=True)
    description    = models.CharField(max_length=300, blank=True)
    rejection_note = models.TextField(blank=True)
    approved_by    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                       on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name='approved_payments')
    approved_at    = models.DateTimeField(null=True, blank=True)
    created_by     = models.ForeignKey(settings.AUTH_USER_MODEL,
                                       on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name='created_payments')
    created_at     = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PMT {self.reference}  ₦{self.amount:,.2f}  [{self.status}]"


# ── Parent Billing ────────────────────────────────────────────────────────────
class ParentBilling(TenantModelMixin, models.Model):
    wallet         = models.ForeignKey(Wallet, on_delete=models.PROTECT,
                                       related_name='billings')
    session        = models.ForeignKey(AcademicSession, on_delete=models.PROTECT)
    term           = models.ForeignKey(Term, on_delete=models.PROTECT)
    total_expected = models.DecimalField(max_digits=14, decimal_places=2,
                                         default=Decimal('0.00'))
    total_paid     = models.DecimalField(max_digits=14, decimal_places=2,
                                         default=Decimal('0.00'))

    class Meta:
        unique_together = ('wallet','session','term')
        ordering = ['-session__name','term__name']

    @property
    def balance(self):
        return max(Decimal('0'), self.total_expected - self.total_paid)

    def refresh_from_children(self):
        children = ChildBilling.objects.filter(parent_billing=self)
        self.total_expected = sum(c.total_fee for c in children)
        self.total_paid     = sum(c.paid for c in children)
        self.save(update_fields=['total_expected','total_paid'])

    def __str__(self):
        return (f"Billing {self.wallet.student.full_name} — "
                f"{self.term} {self.session}  due ₦{self.balance:,.2f}")


# ── Child Billing ─────────────────────────────────────────────────────────────
class ChildBilling(TenantModelMixin, models.Model):
    student        = models.ForeignKey(Student, on_delete=models.PROTECT,
                                       related_name='child_billings')
    parent_billing = models.ForeignKey(ParentBilling, on_delete=models.CASCADE,
                                       related_name='children')
    total_fee      = models.DecimalField(max_digits=14, decimal_places=2,
                                         default=Decimal('0.00'))
    paid           = models.DecimalField(max_digits=14, decimal_places=2,
                                         default=Decimal('0.00'))

    class Meta:
        unique_together = ('student','parent_billing')
        ordering = ['student__full_name']

    @property
    def balance(self):
        return max(Decimal('0'), self.total_fee - self.paid)

    @property
    def is_fully_paid(self):
        return self.paid >= self.total_fee

    def __str__(self):
        return (f"{self.student.full_name}  "
                f"fee ₦{self.total_fee:,.2f}  paid ₦{self.paid:,.2f}")


# ── Child Payment Allocation ──────────────────────────────────────────────────
class ChildPaymentAllocation(TenantModelMixin, models.Model):
    payment          = models.ForeignKey(Payment, on_delete=models.PROTECT,
                                         related_name='allocations')
    child_billing    = models.ForeignKey(ChildBilling, on_delete=models.PROTECT,
                                         related_name='allocations')
    amount_allocated = models.DecimalField(max_digits=14, decimal_places=2)
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (f"Alloc ₦{self.amount_allocated:,.2f} → "
                f"{self.child_billing.student.full_name}")


# ── Installment ───────────────────────────────────────────────────────────────
class Installment(TenantModelMixin, models.Model):
    payment     = models.ForeignKey(Payment, on_delete=models.PROTECT,
                                    related_name='installments')
    invoice     = models.ForeignKey(Invoice, on_delete=models.PROTECT,
                                    related_name='installments',
                                    null=True, blank=True)
    wallet      = models.ForeignKey(Wallet, on_delete=models.PROTECT,
                                    related_name='installments')
    amount      = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=300, blank=True)
    paid_at     = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-paid_at']

    def __str__(self):
        return f"Installment ₦{self.amount:,.2f}  {self.paid_at:%d %b %Y}"


# ── Fee Payment ───────────────────────────────────────────────────────────────
class FeePayment(TenantModelMixin, models.Model):
    STATUS_CHOICES = [
        ('PAID','Paid'),('PARTIAL','Partial'),
        ('UNPAID','Unpaid'),('WAIVED','Waived'),
    ]
    student       = models.ForeignKey(Student, on_delete=models.PROTECT,
                                      related_name='fee_payments')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.PROTECT)
    amount_paid   = models.DecimalField(max_digits=14, decimal_places=2,
                                        default=Decimal('0.00'))
    balance_due   = models.DecimalField(max_digits=14, decimal_places=2,
                                        default=Decimal('0.00'))
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                     default='UNPAID')
    transaction   = models.ForeignKey(Transaction, on_delete=models.SET_NULL,
                                      null=True, blank=True,
                                      related_name='fee_payments')
    paid_at       = models.DateTimeField(null=True, blank=True)
    waived_by     = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.SET_NULL,
                                      null=True, blank=True)
    note          = models.TextField(blank=True)

    class Meta:
        ordering = ['-paid_at']
        unique_together = ('student','fee_structure')

    def __str__(self):
        return f"{self.student.full_name} — {self.fee_structure.name}  [{self.status}]"


# ── Purchase ──────────────────────────────────────────────────────────────────
class Purchase(TenantModelMixin, models.Model):
    STATUS_CHOICES = [
        ('PAID','Paid'),('CANCELLED','Cancelled'),('REFUNDED','Refunded'),
    ]
    student     = models.ForeignKey(Student, on_delete=models.PROTECT,
                                    related_name='purchases')
    item        = models.ForeignKey(SchoolItem, on_delete=models.PROTECT)
    quantity    = models.PositiveIntegerField(default=1)
    unit_price  = models.DecimalField(max_digits=14, decimal_places=2)
    total_price = models.DecimalField(max_digits=14, decimal_places=2)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                   default='PAID')
    transaction = models.OneToOneField(Transaction, on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name='purchase')
    created_at  = models.DateTimeField(default=timezone.now)
    note        = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.full_name} – {self.item.name} x{self.quantity}"


# ── Top-Up Request ────────────────────────────────────────────────────────────
class TopUpRequest(TenantModelMixin, models.Model):
    STATUS_CHOICES = [
        ('PENDING','Pending'),('APPROVED','Approved'),('REJECTED','Rejected'),
    ]
    METHOD_CHOICES = [
        ('CASH','Cash'),('BANK_TRANSFER','Bank Transfer'),
        ('PAYSTACK','Paystack'),('POS','POS / Card'),
    ]
    wallet        = models.ForeignKey(Wallet, on_delete=models.PROTECT,
                                      related_name='topup_requests')
    amount        = models.DecimalField(max_digits=14, decimal_places=2)
    method        = models.CharField(max_length=20, choices=METHOD_CHOICES,
                                     default='CASH')
    payment_proof = models.ImageField(upload_to='topup_proofs/', blank=True, null=True)
    reference     = models.CharField(max_length=100, blank=True)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                     default='PENDING')
    requested_at  = models.DateTimeField(default=timezone.now)
    reviewed_by   = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.SET_NULL,
                                      null=True, blank=True,
                                      related_name='reviewed_topups')
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    note          = models.TextField(blank=True)
    transaction   = models.OneToOneField(Transaction, on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name='topup')

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"TopUp ₦{self.amount:,.2f}  {self.wallet.student.full_name}  [{self.status}]"


# ── Audit Log ─────────────────────────────────────────────────────────────────
class AuditLog(TenantModelMixin, models.Model):
    ACTION_CHOICES = [
        ('PAYMENT_APPROVE','Payment Approved'),('PAYMENT_REJECT','Payment Rejected'),
        ('TOPUP_APPROVE','Top-Up Approved'),('TOPUP_REJECT','Top-Up Rejected'),
        ('WALLET_CREDIT','Wallet Credited'),('WALLET_DEBIT','Wallet Debited'),
        ('INVOICE_CREATE','Invoice Created'),('FEE_WAIVE','Fee Waived'),
        ('SALARY_PAY','Salary Paid'),('OTHER','Other'),
    ]
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.SET_NULL,
                                     null=True, blank=True)
    action       = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_model = models.CharField(max_length=50, blank=True)
    target_id    = models.PositiveIntegerField(null=True, blank=True)
    description  = models.TextField()
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action}  by {self.performed_by}  {self.created_at:%d %b %Y %H:%M}"
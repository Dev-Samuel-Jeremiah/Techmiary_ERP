"""
users/models.py — tenant-scoped
Every model (except User itself) now carries a `tenant` FK via TenantModelMixin.
The User row is shared platform-wide; scope is via Staff/Student profile.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import date
import random, string

from tenants.managers import TenantModelMixin, TenantManager


class User(AbstractUser):
    is_staff_user    = models.BooleanField(default=False)
    is_student       = models.BooleanField(default=False)
    is_parent        = models.BooleanField(default=False)
    restricted       = models.BooleanField(default=False)
    term_password    = models.CharField(max_length=128, blank=True)
    can_create_course = models.BooleanField(default=False)
    can_create_exam   = models.BooleanField(default=False)
    # Tenant this user belongs to — NULL only for platform superadmins
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='users',
        db_index=True,
    )

    def __str__(self):
        return self.username

    @property
    def staff(self):
        """Return this user's Staff profile for the current tenant."""
        from tenants.middleware import get_current_tenant
        tenant = get_current_tenant()
        if tenant:
            return self.staff_profiles.filter(tenant=tenant).first()
        return self.staff_profiles.first()

    @property
    def student(self):
        """Return this user's Student profile for the current tenant."""
        from tenants.middleware import get_current_tenant
        tenant = get_current_tenant()
        if tenant:
            return self.student_profiles.filter(tenant=tenant).first()
        return self.student_profiles.first()


class Staff(TenantModelMixin, models.Model):
    ROLE_CHOICES = [
        ('ADMIN','Administrator'),('TEACHER','Teacher'),
        ('ACCOUNT','Account Officer'),('LIB','Librarian'),
    ]
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='staff_profiles')
    full_name = models.CharField(max_length=255)
    role      = models.CharField(max_length=20, choices=ROLE_CHOICES, default='TEACHER')
    can_generate_password = models.BooleanField(default=False)
    can_create_staff      = models.BooleanField(default=False)
    can_manage_students   = models.BooleanField(default=True)
    can_manage_exams      = models.BooleanField(default=False)
    can_view_all_exams    = models.BooleanField(default=False)
    can_enter_scores      = models.BooleanField(default=False)
    can_view_all_results  = models.BooleanField(default=False)
    can_publish_results   = models.BooleanField(default=False)
    can_access_finance    = models.BooleanField(default=False)
    can_approve_payments  = models.BooleanField(default=False)
    can_access_hostel     = models.BooleanField(default=False)
    can_manage_boarders   = models.BooleanField(default=False)
    can_send_messages     = models.BooleanField(default=False)
    can_mark_attendance   = models.BooleanField(default=False)
    can_access_inventory  = models.BooleanField(default=False)
    objects = TenantManager()
    class Meta:
        unique_together = ('tenant', 'user')
    def __str__(self):
        return f"{self.full_name} ({self.role})"


class Class(TenantModelMixin, models.Model):
    name        = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    objects = TenantManager()
    class Meta:
        unique_together = ('tenant', 'name')
        verbose_name_plural = 'Classes'
    def __str__(self):
        return self.name


STATUS_OPTIONS  = [('Active','Active'),('Graduated','Graduated'),('Withdrawn','Withdrawn')]
TERM_OPTIONS    = [('1st Term','1st Term'),('2nd Term','2nd Term'),('3rd Term','3rd Term')]
GENDER_OPTIONS  = [('Male','Male'),('Female','Female')]


class Student(TenantModelMixin, models.Model):
    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_profiles')
    full_name        = models.CharField(max_length=255)
    gender           = models.CharField(max_length=10, choices=GENDER_OPTIONS, blank=True, null=True)
    date_of_birth    = models.DateField(blank=True, null=True)
    admission_number = models.CharField(max_length=30)
    class_assigned   = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True)
    status           = models.CharField(max_length=20, choices=STATUS_OPTIONS, default='Active')
    current_term     = models.CharField(max_length=20, choices=TERM_OPTIONS, default='1st Term')
    current_session  = models.ForeignKey('academics.AcademicSession', on_delete=models.SET_NULL,
                        null=True, blank=True, related_name='students')
    passport         = models.ImageField(upload_to='student_passports/', blank=True, null=True)
    parent_name          = models.CharField(max_length=255, blank=True, null=True)
    parent_phone         = models.CharField(max_length=20, blank=True, null=True)
    parent_email         = models.EmailField(blank=True, null=True)
    parent_term_password = models.CharField(max_length=128, blank=True, null=True)
    address          = models.TextField(blank=True, null=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    objects = TenantManager()
    class Meta:
        unique_together = ('tenant', 'admission_number')
    def __str__(self):
        return f"{self.full_name} ({self.admission_number})"
    def generate_term_password(self):
        sp = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        pp = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        self.user.set_password(sp); self.user.term_password = sp; self.user.save()
        self.parent_term_password = pp
        return sp, pp
    @property
    def age(self):
        if self.date_of_birth:
            t = date.today()
            return t.year - self.date_of_birth.year - (
                (t.month, t.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None


class Subject(TenantModelMixin, models.Model):
    name        = models.CharField(max_length=100)
    code        = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    objects = TenantManager()
    class Meta:
        unique_together = ('tenant', 'name')
    def __str__(self):
        return self.name


class ClassSubject(TenantModelMixin, models.Model):
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='class_subjects')
    subject      = models.ForeignKey(Subject, on_delete=models.CASCADE)
    objects = TenantManager()
    class Meta:
        unique_together = ('tenant', 'school_class', 'subject')
    def __str__(self):
        return f"{self.school_class} – {self.subject}"


class StudentSubject(TenantModelMixin, models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='student_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    objects = TenantManager()
    class Meta:
        unique_together = ('tenant', 'student', 'subject')


class StaffSubjectClass(TenantModelMixin, models.Model):
    staff        = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='subject_classes')
    subject      = models.ForeignKey(Subject, on_delete=models.CASCADE)
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE)
    objects = TenantManager()
    class Meta:
        unique_together = ('tenant', 'staff', 'subject', 'school_class')
    def __str__(self):
        return f"{self.staff.full_name} – {self.subject.name} ({self.school_class.name})"


ATTENDANCE_STATUS = [('P','Present'),('A','Absent')]


class Attendance(TenantModelMixin, models.Model):
    student      = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='attendances')
    subject      = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    date         = models.DateField(default=timezone.now)
    status       = models.CharField(max_length=1, choices=ATTENDANCE_STATUS, default='P')
    remarks      = models.TextField(blank=True, null=True)
    objects = TenantManager()
    class Meta:
        unique_together = ('tenant','student','school_class','subject','date')
        ordering = ['-date']
    def __str__(self):
        return f"{self.student.full_name} – {self.date} – {self.status}"


PROMOTION_ACTION_CHOICES = [
    ('PROMOTED','Promoted'),('RETURNED','Returned / Repeated'),
    ('GRADUATED','Graduated'),('WITHDRAWN','Withdrawn'),
]


class StudentPromotionRecord(TenantModelMixin, models.Model):
    student      = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='promotion_records')
    promoted_by  = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    from_class   = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='promotions_from')
    from_term    = models.CharField(max_length=20)
    from_session = models.ForeignKey('academics.AcademicSession', on_delete=models.SET_NULL, null=True, related_name='promotions_from')
    to_class     = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='promotions_to')
    to_term      = models.CharField(max_length=20)
    to_session   = models.ForeignKey('academics.AcademicSession', on_delete=models.SET_NULL, null=True, related_name='promotions_to')
    action       = models.CharField(max_length=20, choices=PROMOTION_ACTION_CHOICES, default='PROMOTED')
    note         = models.TextField(blank=True)
    promoted_at  = models.DateTimeField(auto_now_add=True)
    objects = TenantManager()
    class Meta:
        ordering = ['-promoted_at']
    def __str__(self):
        return f"{self.student.full_name}: {self.from_class} → {self.to_class}"
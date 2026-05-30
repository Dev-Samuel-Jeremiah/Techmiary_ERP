from decimal import Decimal

from django.db import models

from academics.models import AcademicSession, Term
from users.models import Class, Student, Subject
from tenants.managers import TenantModelMixin, TenantManager


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

class Grading(TenantModelMixin, models.Model):
    """
    Maps a minimum score to a grade letter and description.
    Example: grade='A', min_score=70, description='Excellent'
    """
    grade       = models.CharField(max_length=2)
    min_score   = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering        = ['-min_score']
        unique_together = ('grade', 'min_score')

    def __str__(self):
        return f"{self.grade} ({self.min_score}+)"

    def includes(self, score: float) -> bool:
        """Return True if *score* falls into this grade band."""
        return Decimal(str(score)) >= self.min_score


# ---------------------------------------------------------------------------
# Term Result
# ---------------------------------------------------------------------------

class TermResult(TenantModelMixin, models.Model):
    student        = models.ForeignKey(Student,         on_delete=models.CASCADE)
    class_assigned = models.ForeignKey(Class,           on_delete=models.CASCADE)
    subject        = models.ForeignKey(Subject,         on_delete=models.CASCADE)
    session        = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    term           = models.ForeignKey(Term,            on_delete=models.CASCADE)

    # Continuous Assessment
    ca1_score   = models.FloatField(default=0)   # TRT
    ca2_score   = models.FloatField(default=0)   # Home Work
    ca3_score   = models.FloatField(default=0)   # Class Participation
    essay_score = models.FloatField(default=0)

    # Exam score (70%)
    exam_score     = models.FloatField(default=0)
    raw_exam_score = models.FloatField(default=0, null=True, blank=True)  # locked CBT score

    # Computed — written by save()
    total_score = models.FloatField(default=0)
    grade       = models.CharField(max_length=5,   blank=True, null=True)  # 'ABS' needs 3
    remark      = models.CharField(max_length=100, blank=True, null=True)

    published = models.BooleanField(default=False)

    # Set True when the student does NOT offer this subject this term.
    # Scores are zeroed, grade becomes 'ABS', and this row is excluded
    # from class averages, highest/lowest, and position calculations.
    is_not_offering = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'subject', 'term', 'session')

    def calculate_total(self) -> float:
        if self.is_not_offering:
            return 0
        return (
            (self.ca1_score   or 0) +
            (self.ca2_score   or 0) +
            (self.ca3_score   or 0) +
            (self.essay_score or 0) +
            (self.exam_score  or 0)
        )

    def calculate_grade_and_remark(self):
        if self.is_not_offering:
            return 'ABS', 'Not Offering'
        grading = (
            Grading.objects
            .filter(min_score__lte=Decimal(str(self.total_score)))
            .order_by('-min_score')
            .first()
        )
        if grading:
            return grading.grade, grading.description or grading.grade
        return None, None

    def save(self, *args, **kwargs):
        if self.is_not_offering:
            # Zero out all scores — never store real scores for non-offering students
            self.ca1_score = self.ca2_score = self.ca3_score = 0
            self.essay_score = self.exam_score = 0
        self.total_score = self.calculate_total()
        self.grade, self.remark = self.calculate_grade_and_remark()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.term})"


# ---------------------------------------------------------------------------
# Session Result  (annual summary across all three terms)
# ---------------------------------------------------------------------------

class SessionResult(TenantModelMixin, models.Model):
    student        = models.ForeignKey(Student,         on_delete=models.CASCADE)
    class_assigned = models.ForeignKey(Class,           on_delete=models.CASCADE)
    subject        = models.ForeignKey(Subject,         on_delete=models.CASCADE)
    session        = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)

    first_term    = models.FloatField(default=0)
    second_term   = models.FloatField(default=0)
    third_term    = models.FloatField(default=0)
    total_score   = models.FloatField(default=0)
    average_score = models.FloatField(default=0)

    class Meta:
        unique_together = ('student', 'subject', 'session')

    def calculate(self):
        self.total_score   = (self.first_term or 0) + (self.second_term or 0) + (self.third_term or 0)
        self.average_score = self.total_score / 3

    def save(self, *args, **kwargs):
        self.calculate()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.session})"


# ---------------------------------------------------------------------------
# Remarks
# ---------------------------------------------------------------------------

class TeacherRemark(TenantModelMixin, models.Model):
    """Class teacher's end-of-term comment on a student."""
    student = models.ForeignKey(Student,         on_delete=models.CASCADE)
    term    = models.ForeignKey(Term,            on_delete=models.CASCADE, blank=True, null=True)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    remark  = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        unique_together = ('student', 'term', 'session')

    def __str__(self):
        return f"Teacher Remark - {self.student} ({self.term} / {self.session})"


class HosRemark(TenantModelMixin, models.Model):
    """Head of School remark on a student's term result."""
    student    = models.ForeignKey(Student,         on_delete=models.CASCADE, related_name='hos_remarks')
    term       = models.ForeignKey(Term,            on_delete=models.CASCADE, blank=True, null=True)
    session    = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    remark     = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'term', 'session')

    def __str__(self):
        return f"HOS Remark - {self.student} ({self.term} / {self.session})"


class SubjectTeacherRemark(TenantModelMixin, models.Model):
    """Per-subject remark written by the subject teacher."""
    student    = models.ForeignKey(Student,         on_delete=models.CASCADE)
    subject    = models.ForeignKey(Subject,         on_delete=models.CASCADE)
    term       = models.ForeignKey(Term,            on_delete=models.CASCADE)
    session    = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    remark     = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject', 'term', 'session')

    def __str__(self):
        return f"Subject Remark - {self.student} / {self.subject} ({self.term})"


# ---------------------------------------------------------------------------
# Skills & Behaviour
# ---------------------------------------------------------------------------

class Skill(TenantModelMixin, models.Model):
    CATEGORY_CHOICES = [
        ('skill',     'Skill'),
        ('behaviour', 'Behaviour'),
    ]
    name     = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class SkillAssessment(TenantModelMixin, models.Model):
    student = models.ForeignKey(Student,         on_delete=models.CASCADE)
    term    = models.ForeignKey(Term,            on_delete=models.CASCADE)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    skill   = models.ForeignKey(Skill,           on_delete=models.CASCADE)
    score   = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])

    class Meta:
        unique_together = ('student', 'term', 'session', 'skill')

    def __str__(self):
        return f"{self.student} - {self.skill.name}: {self.score}"


# ---------------------------------------------------------------------------
# Head Teacher Signature
# ---------------------------------------------------------------------------

class HeadTeacherSignature(TenantModelMixin, models.Model):
    signature = models.ImageField(upload_to='head_teacher_signature/')

    def __str__(self):
        return 'Head Teacher Signature'
    



# ---------------------------------------------------------------------------
# Manual Term Attendance  (days present per student per term)
# ---------------------------------------------------------------------------

class StudentTermAttendance(TenantModelMixin, models.Model):
    """
    Stores how many days a student was present in a given term.
    This overrides the automatic day-count from the Attendance log
    when the result sheet is rendered.
    """
    student = models.ForeignKey(Student,         on_delete=models.CASCADE, related_name='term_attendances')
    term    = models.ForeignKey(Term,            on_delete=models.CASCADE)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE)
    days_present = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ('student', 'term', 'session')
        ordering = ['student__user__last_name', 'student__user__first_name']

    def __str__(self):
        return f"{self.student.full_name} — {self.term} / {self.session}: {self.days_present} days"

# ---------------------------------------------------------------------------
# AI-Generated Student Comments
# ---------------------------------------------------------------------------

class AIStudentComment(TenantModelMixin, models.Model):
    """
    Stores the AI-generated end-of-term comments for a student.

    One record per student per term per session (unique_together).
    Comments are generated via the Anthropic Claude API and can be
    re-generated at any time without affecting the TermResult records.

    Fields:
        teacher_comment  — class teacher's remark (2–3 sentences)
        hos_comment      — Head of School's formal remark (1–2 sentences)
        overall_summary  — one-line holistic summary for the report card header

    generation_ok=False means the last generation attempt failed; check
    error_message for details. The comment fields will be empty in that case.
    """
    student = models.ForeignKey(
        'users.Student', on_delete=models.CASCADE, related_name='ai_comments'
    )
    term    = models.ForeignKey('academics.Term',            on_delete=models.CASCADE)
    session = models.ForeignKey('academics.AcademicSession', on_delete=models.CASCADE)

    # Generated comment fields
    teacher_comment = models.TextField(blank=True, default='')
    hos_comment     = models.TextField(blank=True, default='')
    overall_summary = models.TextField(blank=True, default='')

    # Snapshot used for generation (informational / re-generation detection)
    overall_percentage = models.FloatField(default=0)
    total_subjects     = models.PositiveSmallIntegerField(default=0)

    # Generation metadata
    generated_at  = models.DateTimeField(default=None, null=True, blank=True)
    model_used    = models.CharField(max_length=60, default='claude-sonnet-4-20250514')
    generation_ok = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('student', 'term', 'session')
        ordering        = ['-generated_at']

    def __str__(self):
        status = '✓' if self.generation_ok else '✗'
        return (
            f"[{status}] AI Comment — {self.student.full_name} "
            f"({self.term} / {self.session})"
        )
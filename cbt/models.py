from django.db import models
from django.utils import timezone
from users.models import Student, Class, Staff, Subject
from academics.models import AcademicSession, Term
from django.core.validators import FileExtensionValidator
from tenants.managers import TenantModelMixin, TenantManager
# ----------------------------
# Main Exam
# ----------------------------
class Exam(TenantModelMixin, models.Model):
    EXAM_TYPES = (
        ('CA1', 'First Continuous Assessment'),
        ('CA2', 'Second Continuous Assessment'),
        ('EXAM', 'Exam'),
    )

    title = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, null=True, blank=True)
    term = models.ForeignKey(Term, on_delete=models.CASCADE, null=True, blank=True)
    classes = models.ManyToManyField(Class, related_name='exams')

    exam_type = models.CharField(max_length=4, choices=EXAM_TYPES, default='EXAM')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    published = models.BooleanField(default=False)
    duration_minutes = models.PositiveIntegerField(default=0)
    shuffle_questions = models.BooleanField(default=False)
    allow_retake = models.BooleanField(default=False)

    objects = TenantManager()

    def __str__(self):
        return f"{self.title} ({self.exam_type})"

    @property
    def is_active(self):
        now = timezone.now()
        return self.published and self.start_time <= now <= self.end_time

    @property
    def is_past(self):
        return timezone.now() > self.end_time

    @property
    def is_upcoming(self):
        return timezone.now() < self.start_time

    @property
    def total_marks(self):
        return sum(part.total_marks for part in self.parts.all())


# ----------------------------
# Exam Parts (CBT or Essay)
# ----------------------------
class ExamPart(models.Model):
    PART_TYPES = (
        ('CBT', 'Computer Based Test'),
        ('ESSAY', 'Essay / Written'),
    )

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name='parts'
    )
    part_type = models.CharField(max_length=10, choices=PART_TYPES)
    total_marks = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.exam.title} - {self.part_type}"


# ----------------------------
# CBT Questions
# ----------------------------
class Question(models.Model):
    QUESTION_TYPES = (
        ('MCQ', 'Multiple Choice'),
        ('TF', 'True / False'),
        ('SA', 'Short Answer'),
    )

    exam_part = models.ForeignKey(
        ExamPart,
        on_delete=models.CASCADE,
        related_name='questions'
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        editable=False,
        null=True,
    )
        # NEW FIELDS - Add these
    passage = models.TextField(
        blank=True, 
        null=True,
        help_text="Reading passage or comprehension text for this question"
    )
    
    passage_title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Title of the passage (optional)"
    )
    
    image = models.ImageField(
        upload_to='question_images/%Y/%m/%d/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
        help_text="Upload an image for this question"
    )
    
    image_caption = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Caption for the image (optional)"
    )
    
    # For grouping questions under same passage
    passage_group = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Group ID for questions sharing the same passage (e.g., 'passage_1')"
    )
    
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['exam_part', 'id']
    
    def __str__(self):
        return f"{self.exam_part.exam.title} - Q{self.id}"

    question_text = models.TextField()
    question_type = models.CharField(max_length=5, choices=QUESTION_TYPES, null=True, blank=True)
    marks = models.FloatField(default=1.0)

    def save(self, *args, **kwargs):
        if self.exam_part and self.exam_part.exam:
            self.subject = self.exam_part.exam.subject
        if self.exam_part.part_type == 'ESSAY':
            self.question_type = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.question_text[:60]


# ----------------------------
# CBT Options
# ----------------------------
class Option(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options'
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


# ----------------------------
# Exam Attempt
# ----------------------------
class ExamAttempt(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam_part = models.ForeignKey(ExamPart, on_delete=models.CASCADE)
 
    score = models.FloatField(default=0)
    completed = models.BooleanField(default=False)
 
    retake_number = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
 
    # ── Resume state ──────────────────────────────────────────────────
    # Tracks the last question the student was on so we can resume after
    # a power cut, browser crash, or network failure.
    last_question_index = models.PositiveIntegerField(default=0)
 
    # Tracks elapsed seconds at the moment of last auto-save.
    # On resume, remaining = total_duration_seconds - elapsed_seconds_at_last_save
    # This prevents students getting extra time from reconnecting.
    elapsed_seconds = models.PositiveIntegerField(default=0)
 
    # ISO timestamp of last auto-save (for display / debugging)
    last_autosave_at = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'exam_part'],
                name='unique_student_exam_part_attempt'
            )
        ]
        indexes = [
            models.Index(fields=['student', 'exam_part']),
        ]
 
    def __str__(self):
        return f"{self.student} - {self.exam_part}"
 
    @property
    def time_taken(self):
        if self.submitted_at:
            return (self.submitted_at - self.started_at).total_seconds() / 60
        return None
 


# ----------------------------
# Student Answers (CBT)
# ----------------------------
class StudentAnswer(models.Model):
    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(
        Option,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    text_answer = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f"{self.attempt.student} - {self.question}"


# ----------------------------
# Essay Scores
# ----------------------------
class EssayScore(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    exam_part = models.ForeignKey(
        ExamPart,
        on_delete=models.CASCADE,
        related_name='essay_scores'
    )
    score = models.FloatField(default=0)
    text_answer = models.TextField(null=True, blank=True)  # store student's essay

    class Meta:
        unique_together = ('student', 'exam_part')

    def __str__(self):
        return f"{self.student} - {self.exam_part}"

class ExamStudentRestriction(models.Model):
    """
    When this record exists for an exam, ONLY the listed students
    can see/take that exam (even if the exam is published to their class).
    If NO records exist for an exam, ALL students in the assigned classes can see it.
    """
    exam     = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='student_restrictions')
    student  = models.ForeignKey('users.Student', on_delete=models.CASCADE, related_name='exam_restrictions')
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        'users.Staff', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='exam_restrictions_added'
    )

    class Meta:
        unique_together = ('exam', 'student')
        ordering = ['student__full_name']

    def __str__(self):
        return f"{self.exam.title} → {self.student.full_name}"
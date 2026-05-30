# classroom/models.py
from django.db import models
from tenants.managers import TenantModelMixin, TenantManager

from django.conf import settings
from users.models import Class  # Your existing Class model

User = settings.AUTH_USER_MODEL

# ------------------ COURSE MODEL ------------------
class Course(TenantModelMixin, models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    class_assigned = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses')
    students = models.ManyToManyField(User, related_name='enrolled_courses', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ------------------ SECTION MODEL ------------------
class Section(TenantModelMixin, models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(help_text="Order of the section in the course")

    class Meta:
        ordering = ['order']
        unique_together = ('course', 'order')

    def __str__(self):
        return f"{self.course.name} - {self.title}"


# ------------------ LESSON MODEL ------------------
class Lesson(TenantModelMixin, models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    video = models.FileField(upload_to="course_videos/")
    duration_minutes = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(help_text="Order of lesson in the section")

    class Meta:
        ordering = ['order']
        unique_together = ('section', 'order')

    def __str__(self):
        return self.title


# ------------------ STUDENT SECTION PROGRESS ------------------
class StudentSectionProgress(TenantModelMixin, models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'section')

    def __str__(self):
        status = "Completed" if self.completed else "In Progress"
        return f"{self.student} - {self.section} ({status})"


# ------------------ LESSON PROGRESS ------------------
class LessonProgress(TenantModelMixin, models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    watched = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'lesson')

    def __str__(self):
        status = "Watched" if self.watched else "Not Watched"
        return f"{self.student} - {self.lesson} ({status})"


# ------------------ MATERIAL MODEL ------------------
class Material(TenantModelMixin, models.Model):
    section = models.ForeignKey(
        Section, 
        on_delete=models.CASCADE, 
        related_name='materials'
    )
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='section_materials/')
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        section_title = self.section.title if self.section else "No Section"
        return f"{section_title} - {self.title}"


class Assignment(TenantModelMixin, models.Model):
    section = models.ForeignKey(
        Section, 
        on_delete=models.CASCADE, 
        related_name='assignments'
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        section_title = self.section.title if self.section else "No Section"
        return f"{section_title} - {self.title}"



# ------------------ QUIZ MODEL ------------------

class Quiz(TenantModelMixin, models.Model):
    section = models.ForeignKey(
        Section, 
        on_delete=models.CASCADE, 
        related_name='quizzes'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    pass_mark = models.PositiveIntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        section_title = self.section.title if self.section else "No Section"
        return f"{section_title} - {self.title}"


# ------------------ ASSIGNMENT QUESTION MODEL ------------------
class AssignmentQuestion(TenantModelMixin, models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.assignment.title} - {self.question_text[:50]}"



# ------------------ QUESTION MODEL ------------------
class Question(TenantModelMixin, models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255, blank=True, null=True)
    option_d = models.CharField(max_length=255, blank=True, null=True)
    correct_option = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C'),('D','D')])

    def __str__(self):
        return f"{self.quiz.title} - {self.question_text[:50]}"


# ------------------ SUBMISSION MODEL ------------------
class Submission(TenantModelMixin, models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE)

    file = models.FileField(
        upload_to='submissions/',
        blank=True,
        null=True
    )

    # NULL means NOT YET SUBMITTED
    submitted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    grade = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ('assignment', 'student')
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.student} - {self.assignment.title}"


class SubmissionAnswer(TenantModelMixin, models.Model):
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(AssignmentQuestion, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('submission', 'question')

    def __str__(self):
        return f"{self.submission.assignment.title} - {self.question.question_text[:50]}"



class QuizSubmission(TenantModelMixin, models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.FloatField(null=True, blank=True)
    total_questions = models.PositiveIntegerField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    

    class Meta:
        unique_together = ("quiz", "student")

    def __str__(self):
        return f"{self.student} - {self.quiz.title}"


class QuizAnswer(TenantModelMixin, models.Model):
    submission = models.ForeignKey(QuizSubmission, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(max_length=1, choices=[('A','A'),('B','B'),('C','C'),('D','D')])

    class Meta:
        unique_together = ("submission", "question")

    def __str__(self):
        return f"{self.submission.student} - {self.question.question_text[:50]}"
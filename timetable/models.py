"""
Timetable Models
================
Supports automatic generation of school timetables using a constraint-based
scheduling algorithm. Handles teacher availability, subject frequency, and
period slots per day.
"""

from django.db import models
from tenants.managers import TenantModelMixin, TenantManager

from django.core.exceptions import ValidationError
from users.models import Staff, Subject, Class


# ---------------------------------------------------------------------------
# Configuration Models
# ---------------------------------------------------------------------------

class TimeSlot(TenantModelMixin, models.Model):
    """A single period slot (e.g. "Period 1: 08:00–08:40")."""
    name = models.CharField(max_length=50, help_text='e.g. "Period 1"')
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveSmallIntegerField(default=0, help_text="Sort order within a day")
    is_break = models.BooleanField(default=False, help_text="Mark as break/lunch – skipped in generation")

    class Meta:
        ordering = ['order', 'start_time']

    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%H:%M')}–{self.end_time.strftime('%H:%M')})"


class TimetableConfiguration(TenantModelMixin, models.Model):
    """Top-level timetable configuration per academic term."""
    DAYS = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
        ('SAT', 'Saturday'),
    ]

    name = models.CharField(max_length=100, unique=True, help_text='e.g. "2024/2025 First Term"')
    active_days = models.JSONField(
        default=list,
        help_text='List of day codes, e.g. ["MON","TUE","WED","THU","FRI"]'
    )
    time_slots = models.ManyToManyField(TimeSlot, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        valid_codes = {d[0] for d in self.DAYS}
        for day in (self.active_days or []):
            if day not in valid_codes:
                raise ValidationError(f"Invalid day code: {day}")

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.is_active:
            TimetableConfiguration.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def get_active_slots(self):
        return self.time_slots.filter(is_break=False).order_by('order', 'start_time')

    def __str__(self):
        return self.name


class TeacherSubjectClass(TenantModelMixin, models.Model):
    """
    Links a teacher to a subject + class and specifies how many times
    per week that subject should appear in the timetable for that class.
    """
    config = models.ForeignKey(
        TimetableConfiguration, on_delete=models.CASCADE,
        related_name='teacher_subject_classes'
    )
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='timetable_assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE)
    periods_per_week = models.PositiveSmallIntegerField(
        default=1,
        help_text="How many times this subject appears per week for this class"
    )

    class Meta:
        unique_together = ('config', 'staff', 'subject', 'school_class')
        ordering = ['school_class__name', 'subject__name']

    def clean(self):
        if self.periods_per_week < 1:
            raise ValidationError("Periods per week must be at least 1.")
        if self.periods_per_week > 30:
            raise ValidationError("Periods per week cannot exceed 30.")

    def __str__(self):
        return (
            f"{self.staff.full_name} → {self.subject.name} "
            f"({self.school_class.name}) × {self.periods_per_week}/wk"
        )


# ---------------------------------------------------------------------------
# Generated Timetable
# ---------------------------------------------------------------------------

DAY_CHOICES = [
    ('MON', 'Monday'),
    ('TUE', 'Tuesday'),
    ('WED', 'Wednesday'),
    ('THU', 'Thursday'),
    ('FRI', 'Friday'),
    ('SAT', 'Saturday'),
]


class GeneratedTimetable(TenantModelMixin, models.Model):
    """Header record for a successfully generated timetable."""
    config = models.ForeignKey(
        TimetableConfiguration, on_delete=models.CASCADE,
        related_name='generated_timetables'
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-generated_at']

    def publish(self):
        GeneratedTimetable.objects.filter(config=self.config).exclude(pk=self.pk).update(is_published=False)
        self.is_published = True
        self.save()

    def __str__(self):
        status = "Published" if self.is_published else "Draft"
        return f"Timetable [{self.config}] – {self.generated_at.strftime('%Y-%m-%d %H:%M')} ({status})"


class TimetableSlot(TenantModelMixin, models.Model):
    """One cell in the generated timetable grid."""
    timetable = models.ForeignKey(
        GeneratedTimetable, on_delete=models.CASCADE, related_name='slots'
    )
    school_class = models.ForeignKey(Class, on_delete=models.CASCADE)
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Staff, on_delete=models.CASCADE)

    class Meta:
        unique_together = (
            ('timetable', 'school_class', 'day', 'time_slot'),  # one subject per class per slot
            ('timetable', 'teacher', 'day', 'time_slot'),       # teacher can't be in two places
        )
        ordering = ['school_class__name', 'day', 'time_slot__order']

    def __str__(self):
        return (
            f"{self.school_class} | {self.day} | {self.time_slot.name} | "
            f"{self.subject.name} ({self.teacher.full_name})"
        )


# ---------------------------------------------------------------------------
# Day Override / Special Schedule (e.g. Friday Computer Club)
# ---------------------------------------------------------------------------

class DayOverride(TenantModelMixin, models.Model):
    """
    Defines a custom day schedule for a specific day of the week.
    Overrides the standard timetable with special time blocks (e.g. early
    close + club time on Fridays).
    """
    OVERRIDE_DAY_CHOICES = DAY_CHOICES

    config = models.ForeignKey(
        TimetableConfiguration, on_delete=models.CASCADE,
        related_name='day_overrides'
    )
    day = models.CharField(max_length=3, choices=OVERRIDE_DAY_CHOICES)
    label = models.CharField(
        max_length=100,
        help_text='Short description, e.g. "Friday – Computer Club Day"'
    )
    description = models.TextField(
        blank=True,
        help_text='Optional longer description shown to students/teachers'
    )
    lessons_end_time = models.TimeField(
        help_text='Time when regular lessons finish (e.g. 12:20 for Friday)'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('config', 'day')
        ordering = ['day']

    def __str__(self):
        return f"{self.get_day_display()} Override: {self.label}"

    def get_special_slots(self):
        return self.special_slots.all().order_by('start_time')


class SpecialSlot(TenantModelMixin, models.Model):
    """
    A custom time block appended to (or replacing part of) a day override.
    Example: Computer Club 12:20–14:10 on Fridays.
    """
    SLOT_TYPE_CHOICES = [
        ('CLUB', 'Club / Extra-curricular'),
        ('ASSEMBLY', 'Assembly'),
        ('SPORT', 'Sport'),
        ('EXAM', 'Exam'),
        ('OTHER', 'Other'),
    ]

    override = models.ForeignKey(
        DayOverride, on_delete=models.CASCADE, related_name='special_slots'
    )
    name = models.CharField(max_length=100, help_text='e.g. "Computer Club"')
    slot_type = models.CharField(max_length=20, choices=SLOT_TYPE_CHOICES, default='CLUB')
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField(max_length=100, blank=True, help_text='e.g. "ICT Lab"')
    supervisor = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='supervised_special_slots'
    )
    notes = models.TextField(blank=True)
    applies_to_all_classes = models.BooleanField(
        default=True,
        help_text='If unchecked, only applies to the selected classes below'
    )
    classes = models.ManyToManyField(
        Class, blank=True,
        help_text='Leave empty if applies to all classes'
    )

    class Meta:
        ordering = ['start_time']

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")

    def __str__(self):
        return (
            f"{self.name} ({self.start_time.strftime('%H:%M')}–"
            f"{self.end_time.strftime('%H:%M')})"
        )
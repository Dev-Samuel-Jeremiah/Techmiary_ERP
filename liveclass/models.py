# liveclass/models.py
import uuid
from django.db import models
from django.conf import settings
from tenants.managers import TenantModelMixin, TenantManager
from classroom.models import Course

User = settings.AUTH_USER_MODEL


class LiveClass(TenantModelMixin, models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('ended', 'Ended'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='live_classes')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_live_classes')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    scheduled_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    room_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"{self.course.name} – {self.title}"

    @property
    def jitsi_room_name(self):
        return f"lms-{self.room_id}"


class LiveClassAttendance(TenantModelMixin, models.Model):
    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='live_class_attendances')
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('live_class', 'student')

    def __str__(self):
        return f"{self.student} @ {self.live_class.title}"


class LiveClassMessage(TenantModelMixin, models.Model):
    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"{self.sender} in {self.live_class.title}: {self.message[:40]}"

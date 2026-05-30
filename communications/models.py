"""
communications/models.py — WDA Parent Communication System
============================================================
Email + SMS campaigns, delivery tracking, message templates,
scheduled sending, opt-out management, communication history.
"""

from django.conf import settings
from django.db import models
from tenants.managers import TenantModelMixin, TenantManager

from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# MESSAGE TEMPLATE  (reusable content)
# ─────────────────────────────────────────────────────────────────────────────

class MessageTemplate(TenantModelMixin, models.Model):
    CATEGORY_CHOICES = [
        ('FEE',        'Fee Reminder'),
        ('HOSTEL',     'Hostel Notice'),
        ('EXAM',       'Exam / Result'),
        ('GENERAL',    'General Announcement'),
        ('ATTENDANCE', 'Attendance Alert'),
        ('EMERGENCY',  'Emergency'),
        ('WELCOME',    'Welcome / Admission'),
        ('CUSTOM',     'Custom'),
    ]

    name        = models.CharField(max_length=200, unique=True)
    category    = models.CharField(max_length=12, choices=CATEGORY_CHOICES,
                                   default='GENERAL')
    subject     = models.CharField(max_length=300,
                                   help_text='Email subject. Can use {{student_name}}, {{school_name}}, {{balance}}, etc.')
    body_email  = models.TextField(
        help_text='HTML email body. Placeholders: {{student_name}}, {{parent_name}}, '
                  '{{class_name}}, {{balance}}, {{school_name}}, {{term}}, {{session}}')
    body_sms    = models.CharField(max_length=800,
                                   help_text='SMS body (max ~5 parts = 800 chars). Same placeholders available.')
    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name}"


# ─────────────────────────────────────────────────────────────────────────────
# COMMUNICATION CAMPAIGN  (one send to a group of recipients)
# ─────────────────────────────────────────────────────────────────────────────

class Campaign(TenantModelMixin, models.Model):
    CHANNEL_CHOICES = [
        ('EMAIL',    'Email Only'),
        ('SMS',      'SMS Only'),
        ('BOTH',     'Email + SMS'),
    ]
    STATUS_CHOICES = [
        ('DRAFT',      'Draft'),
        ('SCHEDULED',  'Scheduled'),
        ('SENDING',    'Sending'),
        ('SENT',       'Sent'),
        ('FAILED',     'Failed'),
        ('CANCELLED',  'Cancelled'),
    ]
    AUDIENCE_CHOICES = [
        ('ALL',         'All Parents'),
        ('CLASS',       'Specific Class'),
        ('BOARDERS',    'Hostel Boarders Only'),
        ('DEBTORS',     'Parents with Unpaid Fees'),
        ('CUSTOM',      'Custom Selection'),
    ]

    title           = models.CharField(max_length=300)
    channel         = models.CharField(max_length=5,  choices=CHANNEL_CHOICES, default='EMAIL')
    audience        = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='ALL')
    school_class    = models.ForeignKey('users.Class', on_delete=models.SET_NULL,
                                        null=True, blank=True,
                                        help_text='Only for CLASS audience')
    template        = models.ForeignKey(MessageTemplate, on_delete=models.SET_NULL,
                                        null=True, blank=True)
    subject         = models.CharField(max_length=300,
                                       help_text='Email subject (auto-filled from template if used)')
    body_email      = models.TextField(blank=True,
                                       help_text='HTML email body')
    body_sms        = models.CharField(max_length=800, blank=True,
                                       help_text='SMS message (max 800 chars)')
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    scheduled_at    = models.DateTimeField(null=True, blank=True,
                                           help_text='Leave blank to send immediately')
    sent_at         = models.DateTimeField(null=True, blank=True)
    created_by      = models.ForeignKey(settings.AUTH_USER_MODEL,
                                        on_delete=models.SET_NULL,
                                        null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    # Stats (denormalised for fast dashboard reads)
    total_recipients  = models.PositiveIntegerField(default=0)
    emails_sent       = models.PositiveIntegerField(default=0)
    emails_failed     = models.PositiveIntegerField(default=0)
    sms_sent          = models.PositiveIntegerField(default=0)
    sms_failed        = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.channel}] {self.title}"

    @property
    def success_rate(self):
        total = self.emails_sent + self.sms_sent
        total_attempts = total + self.emails_failed + self.sms_failed
        return round((total / total_attempts) * 100, 1) if total_attempts > 0 else 0


# ─────────────────────────────────────────────────────────────────────────────
# MESSAGE LOG  (one record per recipient per campaign)
# ─────────────────────────────────────────────────────────────────────────────

class MessageLog(TenantModelMixin, models.Model):
    CHANNEL_CHOICES = [
        ('EMAIL', 'Email'),
        ('SMS',   'SMS'),
    ]
    STATUS_CHOICES = [
        ('PENDING',   'Pending'),
        ('SENT',      'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED',    'Failed'),
        ('BOUNCED',   'Bounced'),
        ('OPTED_OUT', 'Opted Out'),
    ]

    campaign        = models.ForeignKey(Campaign, on_delete=models.CASCADE,
                                        related_name='logs')
    student         = models.ForeignKey('users.Student', on_delete=models.CASCADE,
                                        related_name='message_logs')
    channel         = models.CharField(max_length=5, choices=CHANNEL_CHOICES)
    recipient       = models.CharField(max_length=200,
                                       help_text='Email address or phone number')
    subject         = models.CharField(max_length=300, blank=True)
    body            = models.TextField(blank=True)
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES,
                                       default='PENDING')
    provider_ref    = models.CharField(max_length=200, blank=True,
                                       help_text='Message ID from email/SMS provider')
    error_message   = models.TextField(blank=True)
    sent_at         = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (f"{self.channel} → {self.recipient} "
                f"[{self.status}] — {self.campaign.title[:40]}")


# ─────────────────────────────────────────────────────────────────────────────
# QUICK MESSAGE  (one-off direct message to a single parent)
# ─────────────────────────────────────────────────────────────────────────────

class QuickMessage(TenantModelMixin, models.Model):
    CHANNEL_CHOICES = [
        ('EMAIL', 'Email'),
        ('SMS',   'SMS'),
        ('BOTH',  'Email + SMS'),
    ]
    STATUS_CHOICES = [
        ('SENT',   'Sent'),
        ('FAILED', 'Failed'),
    ]

    student     = models.ForeignKey('users.Student', on_delete=models.CASCADE,
                                    related_name='quick_messages')
    channel     = models.CharField(max_length=5, choices=CHANNEL_CHOICES)
    subject     = models.CharField(max_length=300, blank=True)
    body        = models.TextField()
    status      = models.CharField(max_length=7, choices=STATUS_CHOICES)
    sent_by     = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True)
    error       = models.TextField(blank=True)
    sent_at     = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"Quick {self.channel} → {self.student.full_name}"


# ─────────────────────────────────────────────────────────────────────────────
# OPT-OUT  (parent opts out of SMS or email)
# ─────────────────────────────────────────────────────────────────────────────

class OptOut(TenantModelMixin, models.Model):
    CHANNEL_CHOICES = [
        ('EMAIL', 'Email'),
        ('SMS',   'SMS'),
        ('ALL',   'All Channels'),
    ]

    student     = models.ForeignKey('users.Student', on_delete=models.CASCADE,
                                    related_name='opt_outs')
    channel     = models.CharField(max_length=5, choices=CHANNEL_CHOICES)
    opted_out_at = models.DateTimeField(auto_now_add=True)
    reason      = models.TextField(blank=True)

    class Meta:
        unique_together = ('student', 'channel')

    def __str__(self):
        return f"{self.student.full_name} opted out of {self.channel}"
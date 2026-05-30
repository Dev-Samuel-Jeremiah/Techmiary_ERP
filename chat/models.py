# chat/models.py
from django.db import models
from django.conf import settings
from tenants.managers import TenantModelMixin, TenantManager


class Conversation(TenantModelMixin, models.Model):
    """A 1-to-1 conversation between two users within a tenant."""
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        names = ', '.join(u.get_full_name() or u.username for u in self.participants.all())
        return f"Conversation({names})"

    def other_participant(self, user):
        return self.participants.exclude(id=user.id).first()

    def last_message(self):
        return self.messages.order_by('-sent_at').first()

    def unread_count(self, user):
        return self.messages.filter(is_read=False).exclude(sender=user).count()


class Message(TenantModelMixin, models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages'
    )
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    objects = TenantManager()

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"{self.sender.username}: {self.content[:40]}"


class BlockedMessage(TenantModelMixin, models.Model):
    """Log of messages blocked by the moderation system."""

    CATEGORY_CHOICES = [
        ('sexual',      'Sexual / Explicit Content'),
        ('hate_speech', 'Hate Speech / Discrimination'),
        ('threat',      'Threats / Violence'),
        ('bullying',    'Bullying / Harassment'),
        ('self_harm',   'Self-Harm / Suicide Content'),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='blocked_messages'
    )
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='blocked_messages'
    )
    content = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    matched_pattern = models.CharField(max_length=200, blank=True)
    matched_word = models.CharField(max_length=100, blank=True)
    blocked_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)
    admin_note = models.TextField(blank=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-blocked_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.sender} – {self.blocked_at:%Y-%m-%d %H:%M}"
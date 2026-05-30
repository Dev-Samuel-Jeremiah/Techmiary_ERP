# chat/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Conversation, Message, BlockedMessage


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_participants', 'tenant', 'created_at', 'updated_at']
    list_filter = ['tenant']
    search_fields = ['participants__first_name', 'participants__last_name', 'participants__username']

    def get_participants(self, obj):
        return ', '.join(u.get_full_name() or u.username for u in obj.participants.all())
    get_participants.short_description = 'Participants'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'get_conversation', 'content_preview', 'sent_at', 'is_read', 'tenant']
    list_filter = ['is_read', 'tenant']
    search_fields = ['content', 'sender__first_name', 'sender__last_name']

    def content_preview(self, obj):
        return obj.content[:60]
    content_preview.short_description = 'Message'

    def get_conversation(self, obj):
        return f"Conv #{obj.conversation_id}"
    get_conversation.short_description = 'Conversation'


@admin.register(BlockedMessage)
class BlockedMessageAdmin(admin.ModelAdmin):
    list_display = [
        'blocked_at', 'sender', 'category_badge', 'content_preview',
        'matched_word', 'tenant', 'reviewed'
    ]
    list_filter = ['category', 'reviewed', 'tenant', 'blocked_at']
    search_fields = ['content', 'sender__first_name', 'sender__last_name', 'matched_word']
    readonly_fields = [
        'sender', 'conversation', 'content', 'category', 'matched_pattern',
        'matched_word', 'blocked_at', 'tenant'
    ]
    fields = [
        'sender', 'conversation', 'content', 'category',
        'matched_word', 'matched_pattern', 'blocked_at',
        'tenant', 'reviewed', 'admin_note'
    ]
    actions = ['mark_reviewed']

    def category_badge(self, obj):
        colors = {
            'sexual': '#ef6b73',
            'hate_speech': '#ff8c42',
            'threat': '#ef6b73',
            'bullying': '#f4b942',
            'self_harm': '#9b59b6',
        }
        color = colors.get(obj.category, '#aaa')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{}</span>',
            color,
            obj.get_category_display()
        )
    category_badge.short_description = 'Category'

    def content_preview(self, obj):
        return obj.content[:80]
    content_preview.short_description = 'Blocked Content'

    @admin.action(description='Mark selected as reviewed')
    def mark_reviewed(self, request, queryset):
        queryset.update(reviewed=True)

# chat/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.conv_id = self.scope['url_route']['kwargs']['conv_id']
        self.group_name = f"chat_{self.conv_id}"

        # Verify user is participant
        if not await self.is_participant():
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Mark messages as read on connect
        await self.mark_read()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data.get('type') == 'message':
            content = data.get('content', '').strip()
            if not content or len(content) > 2000:
                return

            # ── Moderation check ──────────────────────────────────────
            from chat.moderation import check_message
            result = check_message(content)

            if not result['allowed']:
                # Log violation
                await self.log_blocked_message(content, result)
                # Send rejection back to sender only
                await self.send(text_data=json.dumps({
                    'type': 'blocked',
                    'category': result['category'],
                    'label': result['label'],
                    'reason': result['reason'],
                }))
                return
            # ─────────────────────────────────────────────────────────

            msg = await self.save_message(content)
            display = await self.get_display_name()

            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'chat_message',
                    'message_id': msg.id,
                    'content': content,
                    'sender_id': self.user.id,
                    'display_name': display,
                    'sent_at': msg.sent_at.strftime('%H:%M'),
                    'date': msg.sent_at.strftime('%b %d'),
                }
            )

        elif data.get('type') == 'read':
            await self.mark_read()
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'messages_read',
                    'reader_id': self.user.id,
                }
            )

        elif data.get('type') == 'typing':
            display = await self.get_display_name()
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'typing_indicator',
                    'sender_id': self.user.id,
                    'display_name': display,
                    'is_typing': data.get('is_typing', False),
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message_id': event['message_id'],
            'content': event['content'],
            'sender_id': event['sender_id'],
            'display_name': event['display_name'],
            'sent_at': event['sent_at'],
            'date': event['date'],
        }))

    async def messages_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read',
            'reader_id': event['reader_id'],
        }))

    async def typing_indicator(self, event):
        if event['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'display_name': event['display_name'],
                'is_typing': event['is_typing'],
            }))

    @database_sync_to_async
    def log_blocked_message(self, content, result):
        from chat.models import Conversation, BlockedMessage
        try:
            conv = Conversation.objects.get(id=self.conv_id)
            BlockedMessage.objects.create(
                sender=self.user,
                conversation=conv,
                content=content,
                category=result['category'],
                matched_pattern=result.get('matched_pattern', ''),
                matched_word=result.get('matched_word', ''),
                tenant=conv.tenant,
            )
        except Exception:
            pass

    @database_sync_to_async
    def is_participant(self):
        from chat.models import Conversation
        try:
            conv = Conversation.objects.get(id=self.conv_id)
            return conv.participants.filter(id=self.user.id).exists()
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content):
        from chat.models import Conversation, Message
        from tenants.middleware import get_current_tenant
        conv = Conversation.objects.get(id=self.conv_id)
        return Message.objects.create(
            conversation=conv,
            sender=self.user,
            content=content,
            tenant=conv.tenant,
        )

    @database_sync_to_async
    def mark_read(self):
        from chat.models import Message
        Message.objects.filter(
            conversation_id=self.conv_id,
            is_read=False,
        ).exclude(sender=self.user).update(is_read=True)

    @database_sync_to_async
    def get_display_name(self):
        full = f"{self.user.first_name} {self.user.last_name}".strip()
        return full or self.user.username


class PresenceConsumer(AsyncWebsocketConsumer):
    """Tracks online users per tenant for the people list."""

    async def connect(self):
        self.user = self.scope['user']
        self.group_name = None  # guard against disconnect before connect completes

        if not self.user.is_authenticated:
            await self.close()
            return

        self.tenant_id = await self.get_tenant_id()
        if not self.tenant_id:
            await self.close()
            return

        self.group_name = f"presence_{self.tenant_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        display = await self.get_display_name()
        await self.channel_layer.group_send(self.group_name, {
            'type': 'presence_update',
            'user_id': self.user.id,
            'display_name': display,
            'status': 'online',
        })

    async def disconnect(self, close_code):
        if not self.group_name:
            return  # never fully connected, nothing to clean up
        if self.user.is_authenticated:
            display = await self.get_display_name()
            await self.channel_layer.group_send(self.group_name, {
                'type': 'presence_update',
                'user_id': self.user.id,
                'display_name': display,
                'status': 'offline',
            })
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'presence',
            'user_id': event['user_id'],
            'status': event['status'],
        }))

    @database_sync_to_async
    def get_tenant_id(self):
        """Get tenant from user's Staff or Student profile — works in WS context."""
        from users.models import Staff, Student
        try:
            staff = Staff.objects.filter(user=self.user).first()
            if staff:
                return staff.tenant_id
            student = Student.objects.filter(user=self.user).first()
            if student:
                return student.tenant_id
        except Exception:
            pass
        return None

    @database_sync_to_async
    def get_display_name(self):
        full = f"{self.user.first_name} {self.user.last_name}".strip()
        return full or self.user.username
# liveclass/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class LiveClassConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.group_name = f"liveclass_{self.room_id}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Notify others that someone joined
        display_name = await self.get_display_name()
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "user_event",
                "event": "joined",
                "user_id": self.user.id,
                "display_name": display_name,
            }
        )

    async def disconnect(self, close_code):
        display_name = await self.get_display_name()
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "user_event",
                "event": "left",
                "user_id": self.user.id,
                "display_name": display_name,
            }
        )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get("type")

        if msg_type == "chat_message":
            message = data.get("message", "").strip()
            if not message:
                return
            display_name = await self.get_display_name()
            saved_msg = await self.save_message(message)

            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat_message",
                    "message": message,
                    "user_id": self.user.id,
                    "display_name": display_name,
                    "sent_at": saved_msg.sent_at.strftime("%H:%M"),
                    "is_teacher": await self.is_teacher(),
                }
            )

        elif msg_type == "reaction":
            emoji = data.get("emoji", "")
            display_name = await self.get_display_name()
            ALLOWED = {"👏", "✋", "❤️", "😂", "😮", "🔥"}
            if emoji in ALLOWED:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "reaction",
                        "emoji": emoji,
                        "user_id": self.user.id,
                        "display_name": display_name,
                    }
                )

        elif msg_type == "class_control":
            # Only teacher can start/end class
            if await self.is_teacher():
                action = data.get("action")
                await self.handle_class_control(action)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "message": event["message"],
            "user_id": event["user_id"],
            "display_name": event["display_name"],
            "sent_at": event["sent_at"],
            "is_teacher": event.get("is_teacher", False),
        }))

    async def user_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_event",
            "event": event["event"],
            "user_id": event["user_id"],
            "display_name": event["display_name"],
        }))

    async def reaction(self, event):
        await self.send(text_data=json.dumps({
            "type": "reaction",
            "emoji": event["emoji"],
            "user_id": event["user_id"],
            "display_name": event["display_name"],
        }))

    async def class_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "class_status",
            "status": event["status"],
        }))

    @database_sync_to_async
    def get_display_name(self):
        user = self.user
        full = f"{user.first_name} {user.last_name}".strip()
        return full or user.username

    @database_sync_to_async
    def is_teacher(self):
        from liveclass.models import LiveClass
        try:
            lc = LiveClass.objects.get(room_id=self.room_id)
            return lc.teacher_id == self.user.id
        except LiveClass.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, message):
        from liveclass.models import LiveClass, LiveClassMessage
        lc = LiveClass.objects.get(room_id=self.room_id)
        return LiveClassMessage.objects.create(
            live_class=lc,
            sender=self.user,
            message=message,
            tenant=lc.tenant,
        )

    async def handle_class_control(self, action):
        from channels.db import database_sync_to_async

        @database_sync_to_async
        def update_status():
            from liveclass.models import LiveClass
            try:
                lc = LiveClass.objects.get(room_id=self.room_id)
                if action == "start":
                    lc.status = "live"
                    lc.started_at = timezone.now()
                elif action == "end":
                    lc.status = "ended"
                    lc.ended_at = timezone.now()
                lc.save()
                return lc.status
            except LiveClass.DoesNotExist:
                return None

        new_status = await update_status()
        if new_status:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "class_status",
                    "status": new_status,
                }
            )

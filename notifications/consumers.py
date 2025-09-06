from channels.generic.websocket import AsyncJsonWebsocketConsumer


class NotificationsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        # Join per-user group when authenticated; otherwise fall back to a noop group
        self.group_name = f"user_{user.pk}" if (user and getattr(user, "is_authenticated", False)) else "anon"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Optional hello to help debugging
        await self.send_json({"type": "ws.hello", "user": getattr(user, "pk", None)})

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Called by group_send with type="notify"
    async def notify(self, event):
        await self.send_json(event.get("payload", {}))

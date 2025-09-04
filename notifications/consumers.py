from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async

class NotificationsConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Simple broadcast group; swap to per-user later if you want
        self.group_name = "broadcast"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Will be called by channel_layer.group_send(type="notify", ...)
    async def notify(self, event):
        await self.send_json(event.get("payload", {"ok": True}))

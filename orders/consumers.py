import asyncio
import time
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.apps import apps
from django.utils import timezone

from users.utils import is_vendor_or_staff

Delivery = apps.get_model("orders", "Delivery")
_last_write = {}
_lock = asyncio.Lock()

def _now():
    return time.monotonic()


class DeliveryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.delivery_id = int(self.scope["url_route"]["kwargs"]["delivery_id"])
        self.delivery = await database_sync_to_async(
            Delivery.objects.select_related("order", "driver").get
        )(pk=self.delivery_id)
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4003)
            return
        is_driver = self.delivery.driver_id == getattr(user, "id", None)
        is_owner = self.delivery.order.user_id == getattr(user, "id", None)
        in_vendor = await database_sync_to_async(is_vendor_or_staff)(user)
        if not (is_driver or is_owner or in_vendor):
            await self.close(code=4003)
            return
        self.group = self.delivery.ws_group
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **_):
        if self.scope["user"].id != self.delivery.driver_id:
            return
        typ = content.get("type")
        if typ == "ping":
            lat, lng = content.get("lat"), content.get("lng")
            if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                return
            if not (-90 <= float(lat) <= 90 and -180 <= float(lng) <= 180):
                return
            async with _lock:
                last = _last_write.get(self.delivery_id, 0.0)
                now = _now()
                if now - last >= 2.0:
                    await database_sync_to_async(
                        Delivery.objects.filter(pk=self.delivery_id).update
                    )(last_lat=lat, last_lng=lng, last_ping_at=timezone.now())
                    _last_write[self.delivery_id] = now
            await self.channel_layer.group_send(
                self.group,
                {
                    "type": "position.update",
                    "lat": float(lat),
                    "lng": float(lng),
                    "ts": timezone.now().isoformat(),
                },
            )
        elif typ == "status":
            new = content.get("status")
            valid = [c[0] for c in Delivery.Status.choices]
            if new not in valid:
                return
            async def _upd():
                d = Delivery.objects.select_for_update().get(pk=self.delivery_id)
                d.status = new
                if new == Delivery.Status.PICKED_UP:
                    d.picked_up_at = timezone.now()
                if new == Delivery.Status.DELIVERED:
                    d.delivered_at = timezone.now()
                d.save(update_fields=["status", "picked_up_at", "delivered_at"])
            await database_sync_to_async(_upd)()
            await self.channel_layer.group_send(
                self.group, {"type": "status.update", "status": new}
            )

    async def position_update(self, event):
        await self.send_json(
            {
                "event": "position",
                "lat": event["lat"],
                "lng": event["lng"],
                "ts": event["ts"],
            }
        )

    async def status_update(self, event):
        await self.send_json({"event": "status", "status": event["status"]})

    async def delivery_event(self, event):
        """
        Generic bridge for REST-originated events.
        Input: {"type":"delivery.event","kind":"assign|unassign|accept|status|position", ...payload}
        Output to client: {"event": "<kind>", ...payload}
        """
        kind = event.get("kind")
        payload = {k: v for k, v in event.items() if k not in {"type", "kind"}}
        payload["event"] = kind
        await self.send_json(payload)

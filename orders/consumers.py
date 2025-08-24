from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .models import Delivery

Q6 = Decimal("0.000001")

def in_range(lat, lng):
    try:
        lat = Decimal(str(lat)); lng = Decimal(str(lng))
    except (InvalidOperation, TypeError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    # quantize to 6 dp like your model
    return (lat.quantize(Q6, rounding=ROUND_HALF_UP),
            lng.quantize(Q6, rounding=ROUND_HALF_UP))

class DeliveryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.delivery_id = int(self.scope["url_route"]["kwargs"]["delivery_id"])
        self.group = f"delivery.{self.delivery_id}"

        d = await self._get_delivery()
        if not d:
            await self.close(code=4404); return

        u = self.scope.get("user")
        self.is_authenticated = u and not isinstance(u, AnonymousUser)
        self.is_driver = self.is_authenticated and (u.id == d.driver_id)
        self.can_view = self.is_driver or (self.is_authenticated and (u.is_staff or u.id == d.order.user_id))

        if not self.can_view:
            await self.close(code=4403); return

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """
        Driver -> server:
          {"type":"ping","lat":-1.303,"lng":36.81}
          {"type":"action","action":"picked_up" | "delivered"}
        Viewers never send anything.
        """
        if content.get("type") == "ping":
            if not self.is_driver:  # only the assigned driver can ping
                return
            pair = in_range(content.get("lat"), content.get("lng"))
            if not pair:
                return
            lat, lng = pair
            await self._save_ping(lat, lng)
            await self.channel_layer.group_send(
                self.group,
                {"type": "broadcast", "data": {
                    "event": "driver_ping",
                    "delivery_id": self.delivery_id,
                    "lat": float(lat), "lng": float(lng),
                    "ts": timezone.now().isoformat()
                }}
            )
            await self.send_json({"ok": True})

        elif content.get("type") == "action":
            if not self.is_driver:
                return
            action = content.get("action")
            new_status = None
            fields = {}
            now = timezone.now()
            if action == "picked_up":
                new_status = Delivery.Status.PICKED_UP
                fields["picked_up_at"] = now
            elif action == "delivered":
                new_status = Delivery.Status.DELIVERED
                fields["delivered_at"] = now
            else:
                return
            await self._set_status(new_status, fields)
            await self.channel_layer.group_send(
                self.group,
                {"type": "broadcast", "data": {
                    "event": "status",
                    "delivery_id": self.delivery_id,
                    "status": new_status
                }}
            )
            await self.send_json({"ok": True})

    async def broadcast(self, event):
        await self.send_json(event.get("data", {}))

    # --- DB helpers (sync -> async) ---
    @database_sync_to_async
    def _get_delivery(self):
        try:
            return Delivery.objects.select_related("order").get(pk=self.delivery_id)
        except Delivery.DoesNotExist:
            return None

    @database_sync_to_async
    def _save_ping(self, lat: Decimal, lng: Decimal):
        d = Delivery.objects.get(pk=self.delivery_id)
        d.last_lat = lat
        d.last_lng = lng
        d.last_ping_at = timezone.now()
        d.save(update_fields=["last_lat","last_lng","last_ping_at","updated_at"])

    @database_sync_to_async
    def _set_status(self, status, extra_fields: dict):
        Delivery.objects.filter(pk=self.delivery_id).update(status=status, updated_at=timezone.now(), **extra_fields)

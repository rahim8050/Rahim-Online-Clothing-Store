import time
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from orders.models import Delivery

THROTTLE_SECONDS = 5  # limit DB writes per driver


def _throttle_key(delivery_id, user_id):
    return f"drv:lastpos:{delivery_id}:{user_id}"


class DeliveryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        try:
            self.delivery_id = int(self.scope["url_route"]["kwargs"]["delivery_id"])
        except Exception:
            await self.close(code=4400)
            return

        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        delivery = await self._get_delivery(self.delivery_id)
        if not delivery:
            await self.close(code=4404)
            return

        if not await self._user_can_view(user, delivery):
            await self.close(code=4403)
            return

        self.user = user
        self.is_driver = delivery.driver_id == user.id
        self.group = f"delivery.track.{self.delivery_id}"

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")
        if msg_type not in {"position_update", "status"}:
            await self.send_json({"type": "error", "error": "unsupported_type"})
            return

        if not self.is_driver:
            await self.send_json({"type": "error", "error": "forbidden"})
            return

        if msg_type == "position_update":
            try:
                lat = float(content["lat"])
                lng = float(content["lng"])
            except Exception:
                await self.send_json({"type": "error", "error": "bad_position"})
                return

            # Broadcast standard event schema
            await self.channel_layer.group_send(
                self.group,
                {"type": "broadcast", "payload": {"type": "position_update", "lat": lat, "lng": lng}},
            )

            now = time.time()
            key = _throttle_key(self.delivery_id, self.user.id)
            last = cache.get(key)
            if not last or (now - last) >= THROTTLE_SECONDS:
                cache.set(key, now, timeout=THROTTLE_SECONDS)
                await self._save_position(self.delivery_id, lat, lng)

        else:  # status update
            status = content.get("status")
            if status not in {s[0] for s in Delivery.Status.choices}:
                await self.send_json({"type": "error", "error": "bad_status"})
                return

            await self._update_status(self.delivery_id, status)

            await self.channel_layer.group_send(
                self.group,
                {"type": "broadcast", "payload": {"type": "status", "status": status}},
            )

    async def broadcast(self, event):
        await self.send_json(event["payload"])

    # --- DB helpers ---
    @database_sync_to_async
    def _get_delivery(self, delivery_id):
        try:
            return Delivery.objects.select_related("order").get(pk=delivery_id)
        except Delivery.DoesNotExist:
            return None

    @database_sync_to_async
    def _user_can_view(self, user, delivery):
        return (
            user.is_staff
            or user.id == delivery.order.user_id
            or user.id == delivery.driver_id
        )

    @database_sync_to_async
    def _save_position(self, delivery_id, lat, lng):
        Delivery.objects.filter(pk=delivery_id).update(
            last_lat=lat,
            last_lng=lng,
            last_ping_at=timezone.now(),
            updated_at=timezone.now(),
        )

    @database_sync_to_async
    def _update_status(self, delivery_id, status):
        Delivery.objects.filter(pk=delivery_id).update(
            status=status,
            updated_at=timezone.now(),
        )


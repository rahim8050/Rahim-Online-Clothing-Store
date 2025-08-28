import time
from decimal import Decimal, ROUND_HALF_UP

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser

from orders.models import Delivery

THROTTLE_SECONDS = 5  # DB write throttle per driver
Q6 = Decimal("0.000001")

def _throttle_key(delivery_id, user_id):
    return f"drv:lastpos:{delivery_id}:{user_id}"

def _q6(val):
    if val is None:
        return None
    # JSON numbers arrive as Python floats; use str() to preserve digits
    return Decimal(str(val)).quantize(Q6, rounding=ROUND_HALF_UP)

def _valid_latlng(lat, lng):
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0


class DeliveryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        try:
            self.delivery_id = int(self.scope["url_route"]["kwargs"]["delivery_id"])
        except Exception:
            await self.close(code=4400); return

        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401); return

        delivery = await self._get_delivery(self.delivery_id)
        if not delivery:
            await self.close(code=4404); return

        if not await self._user_can_view(user, delivery):
            await self.close(code=4403); return

        self.user = user
        self.is_driver = (delivery.driver_id == user.id)
        self.group = f"delivery.track.{self.delivery_id}"

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")

        # Normalize message types from the client
        if msg_type in {"ping", "position_update"}:
            if not self.is_driver:
                await self.send_json({"type": "error", "error": "forbidden"}); return

            lat, lng = content.get("lat"), content.get("lng")
            if not _valid_latlng(lat, lng):
                await self.send_json({"type": "error", "error": "bad_position"}); return
            lat_f, lng_f = float(lat), float(lng)

            # Broadcast to watchers (customer/vendor/driver)
            await self.channel_layer.group_send(
                self.group,
                {"type": "broadcast", "payload": {"type": "position_update", "lat": lat_f, "lng": lng_f}},
            )
            # Echo back to sender immediately
            await self.send_json({"type": "position_update", "lat": lat_f, "lng": lng_f})

            # Throttled DB persist
            now = time.time()
            key = _throttle_key(self.delivery_id, self.user.id)
            last = cache.get(key)
            if not last or (now - last) >= THROTTLE_SECONDS:
                cache.set(key, now, timeout=THROTTLE_SECONDS)
                await self._save_position(self.delivery_id, _q6(lat_f), _q6(lng_f))
            return

        if msg_type in {"action", "status"}:
            if not self.is_driver:
                await self.send_json({"type": "error", "error": "forbidden"}); return

            # Map actions to canonical status values
            action = content.get("action")
            status = content.get("status")
            if msg_type == "action":
                if action == "picked_up":
                    status = Delivery.Status.PICKED_UP
                elif action == "delivered":
                    status = Delivery.Status.DELIVERED
                else:
                    await self.send_json({"type": "error", "error": "bad_action"}); return

            if status not in {s[0] for s in Delivery.Status.choices}:
                await self.send_json({"type": "error", "error": "bad_status"}); return

            await self._update_status(self.delivery_id, status)

            # Notify all watchers
            await self.channel_layer.group_send(
                self.group,
                {"type": "broadcast", "payload": {"type": "status", "status": status}},
            )
            return

        await self.send_json({"type": "error", "error": "unsupported_type"})

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
    def _save_position(self, delivery_id, lat_q6, lng_q6):
        Delivery.objects.filter(pk=delivery_id).update(
            last_lat=lat_q6,
            last_lng=lng_q6,
            last_ping_at=timezone.now(),
            updated_at=timezone.now(),
        )

    @database_sync_to_async
    def _update_status(self, delivery_id, status):
        Delivery.objects.filter(pk=delivery_id).update(
            status=status,
            updated_at=timezone.now(),
        )


class DriverConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401); return
        self.group = f"driver.{user.id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    # Broadcast entry point (type must be "driver.event")
    async def driver_event(self, event):
        # You can shape this however your frontend expects:
        # e.g. {"event":"assigned","delivery":{...}}
        await self.send_json(event)

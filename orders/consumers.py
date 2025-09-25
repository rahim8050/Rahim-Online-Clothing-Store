# orders/consumers.py
import logging
import math
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.apps import apps
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

Q6 = Decimal("0.000001")  # 6 dp (~0.11m at equator)


class DeliveryTrackerConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.user_id = int(getattr(user, "id", 0) or 0)
        try:
            self.delivery_id = int(self.scope["url_route"]["kwargs"]["delivery_id"])
        except Exception:
            await self.close()
            return

        # Allow both assigned driver and order owner to subscribe
        if not await self._can_subscribe(self.delivery_id, self.user_id):
            await self.close()
            return

        self.group_name = f"delivery.{self.delivery_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Per-connection throttling state for DB writes
        self._last_saved_at_ms = 0
        self._last_saved_ll = None  # (lat, lng) float tuple

    async def disconnect(self, close_code):
        try:
            if hasattr(self, "group_name"):
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )
        except Exception as e:
            logger.debug("channels discard failed: %s", e, exc_info=True)

    # ---- Incoming messages ----
    async def receive_json(self, content, **kwargs):
        """
        Accepts both legacy and current payloads:

        - {"type":"position_update", "lat": ..., "lng": ...}
        - {"op":"update", "lat": ..., "lng": ...}
        - {"type":"status", "status":"picked_up" | "en_route" | "delivered"}
        - {"op":"ping"}  -> replies {"type":"pong"}
        """
        msg_type = content.get("type") or content.get("op")

        if msg_type in ("position_update", "update", "position"):
            await self._handle_position_update(content)
            return

        if msg_type == "status":
            await self._handle_status_broadcast(content)
            return

        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return

    # ---- Group event fanout ----
    async def delivery_event(self, event):
        kind = event.get("kind")
        if kind == "position_update":
            await self.send_json(
                {
                    "type": "position_update",
                    "lat": event.get("lat"),
                    "lng": event.get("lng"),
                    "status": event.get("status"),
                    "ts": event.get("ts"),
                }
            )
            return
        if kind == "status":
            await self.send_json({"type": "status", "status": event.get("status")})
            return

    async def status_update(self, event):
        # Emitted by post_save signals via group_send(type="status.update")
        await self.send_json(
            {
                "type": "status_update",
                "id": event.get("id"),
                "status": event.get("status"),
                "assigned_at": event.get("assigned_at"),
                "picked_up_at": event.get("picked_up_at"),
                "delivered_at": event.get("delivered_at"),
            }
        )

    # Back-compat for older senders using type="tracker.update"
    async def tracker_update(self, event):
        data = event.get("data", {}) or {}
        await self.send_json({"type": "position_update", **data})

    # Back-compat for staff debug sender using type="broadcast"
    async def broadcast(self, event):
        payload = event.get("payload") or {}
        await self.send_json(payload)

    # ---- Helpers ----
    @staticmethod
    def _haversine_m(a, b):
        (lat1, lng1), (lat2, lng2) = a, b
        R = 6371000.0
        dLat = math.radians(lat2 - lat1)
        dLng = math.radians(lng2 - lng1)
        s1 = (
            math.sin(dLat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dLng / 2) ** 2
        )
        return 2 * R * math.asin(math.sqrt(s1))

    @database_sync_to_async
    def _can_subscribe(self, delivery_id: int, user_id: int) -> bool:
        Delivery = apps.get_model("orders", "Delivery")
        try:
            d = Delivery.objects.select_related("order").get(pk=int(delivery_id))
        except Delivery.DoesNotExist:
            return False
        return (d.driver_id == user_id) or (
            getattr(d.order, "user_id", None) == user_id
        )

    @database_sync_to_async
    def _is_owner_driver(self, delivery_id: int, user_id: int) -> bool:
        try:
            Delivery = apps.get_model("orders", "Delivery")
            return Delivery.objects.filter(
                pk=int(delivery_id), driver_id=user_id
            ).exists()
        except Exception:
            return False

    @database_sync_to_async
    def _save_position(
        self, delivery_id: int, user_id: int, lat: Decimal, lng: Decimal
    ):
        """
        Persist position for the assigned driver.
        Returns (changed: bool, new_status: str|None).
        """
        Delivery = apps.get_model("orders", "Delivery")
        DeliveryPing = apps.get_model("orders", "DeliveryPing")

        try:
            d = Delivery.objects.get(pk=int(delivery_id), driver_id=user_id)
        except Delivery.DoesNotExist:
            return False, None

        changed = False
        new_status = None
        now = timezone.now()

        if d.last_lat != lat or d.last_lng != lng:
            d.last_lat = lat
            d.last_lng = lng
            changed = True

        d.last_ping_at = now

        try:
            if d.status == Delivery.Status.ASSIGNED:
                d.status = Delivery.Status.EN_ROUTE
                new_status = d.status
        except Exception as e:
            # Enum/choices not available? ignore gracefully
            logger.debug("channels discard failed: %s", e, exc_info=True)

        fields = ["last_lat", "last_lng", "last_ping_at", "updated_at"]
        if new_status is not None:
            fields.append("status")
        d.save(update_fields=fields)

        if changed:
            # History + audit (best-effort)
            try:
                DeliveryPing.objects.create(delivery=d, lat=lat, lng=lng)
            except Exception as e:
                logger.debug("channels discard failed: %s", e, exc_info=True)
            try:
                DeliveryEvent = apps.get_model("orders", "DeliveryEvent")
                DeliveryEvent.objects.create(
                    delivery=d,
                    actor_id=user_id,
                    type="position",
                    note={"lat": float(lat), "lng": float(lng)},
                )
            except Exception as e:
                logger.debug("channels discard failed: %s", e, exc_info=True)

        return changed, new_status

    @database_sync_to_async
    def _update_status(self, delivery_id: int, user_id: int, status_new: str) -> bool:
        Delivery = apps.get_model("orders", "Delivery")
        try:
            d = Delivery.objects.get(pk=int(delivery_id), driver_id=user_id)
        except Delivery.DoesNotExist:
            return False

        allowed = {
            Delivery.Status.PICKED_UP,
            Delivery.Status.EN_ROUTE,
            Delivery.Status.DELIVERED,
        }
        if status_new not in allowed:
            return False

        now = timezone.now()
        d.status = status_new
        if status_new == Delivery.Status.PICKED_UP:
            d.picked_up_at = now
        if status_new == Delivery.Status.DELIVERED:
            d.delivered_at = now
        d.save(update_fields=["status", "picked_up_at", "delivered_at", "updated_at"])
        return True

    # ---- Message handlers ----
    async def _handle_position_update(self, content):
        lat_raw = content.get("lat")
        lng_raw = content.get("lng")

        # Only assigned driver can persist/broadcast positions
        if not await self._is_owner_driver(self.delivery_id, self.user_id):
            await self.send_json({"type": "error", "error": "forbidden"})
            return

        # Parse & validate
        try:
            lat_d = Decimal(str(lat_raw)).quantize(Q6, rounding=ROUND_HALF_UP)
            lng_d = Decimal(str(lng_raw)).quantize(Q6, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            await self.send_json({"type": "error", "error": "invalid_payload"})
            return

        if not (
            Decimal("-90") <= lat_d <= Decimal("90")
            and Decimal("-180") <= lng_d <= Decimal("180")
        ):
            await self.send_json({"type": "error", "error": "out_of_range"})
            return

        # Global throttle per (driver, delivery): 5s using cache
        cache_key = f"ws:last:{self.user_id}:{self.delivery_id}"
        last = cache.get(cache_key)
        now_ms = int(timezone.now().timestamp() * 1000)
        if last and (now_ms - int(last)) < 5000:
            return
        cache.set(cache_key, now_ms, timeout=30)

        # Connection throttle: save every â‰¥8s AND after â‰¥25m movement
        due = (now_ms - self._last_saved_at_ms) >= 8000
        lat_f, lng_f = float(lat_d), float(lng_d)
        moved_enough = (
            True
            if self._last_saved_ll is None
            else (self._haversine_m(self._last_saved_ll, (lat_f, lng_f)) >= 25.0)
        )

        # Persist if due + moved
        if due and moved_enough:
            changed, new_status = await self._save_position(
                self.delivery_id, self.user_id, lat_d, lng_d
            )
            if changed:
                self._last_saved_at_ms = now_ms
                self._last_saved_ll = (lat_f, lng_f)
            if new_status is not None:
                await self.channel_layer.group_send(
                    self.group_name,
                    {"type": "delivery.event", "kind": "status", "status": new_status},
                )

        # Always broadcast (after permission checks) for live UX
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "delivery.event",
                "kind": "position_update",
                "lat": lat_f,
                "lng": lng_f,
                "ts": now_ms,
            },
        )

    async def _handle_status_broadcast(self, content):
        status_new = content.get("status")
        if not isinstance(status_new, str) or not status_new:
            return

        # Only the assigned driver can broadcast status hints
        if not await self._is_owner_driver(self.delivery_id, self.user_id):
            await self.send_json({"type": "error", "error": "forbidden"})
            return

        # Pure broadcast (UI hint). To persist, call _update_status instead.
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "delivery.event", "kind": "status", "status": status_new},
        )

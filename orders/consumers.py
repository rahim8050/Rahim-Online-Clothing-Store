from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.core.cache import cache
from django.apps import apps
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math


class DeliveryTrackerConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket tracker for a single delivery.

    - Group: "delivery.<id>"
    - Client messages supported:
        - {type: "position_update", lat, lng}
        - {type: "status", status}
        - {type: "ping"}
    - Outgoing messages to clients:
        - {type: "position_update", lat, lng, [status], [ts]}
        - {type: "status", status}
        - {type: "status_update", ...}  # from signals
    """

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
        # Allow both the assigned driver and the order owner to subscribe (view-only for owner)
        if not await self._can_subscribe(self.delivery_id, self.user_id):
            await self.close()
            return
        self.group_name = f"delivery.{self.delivery_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # per-connection throttle state (for DB writes)
        self._last_saved_at_ms = 0
        self._last_saved_ll = None  # (lat, lng) floats

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    async def receive_json(self, content, **kwargs):
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

        # Back-compat broadcast passthrough
        if msg_type == "broadcast":
            payload = content.get("payload") or {}
            await self.send_json(payload)
            return

    async def delivery_event(self, event):
        # Fan-out group events into client-friendly messages
        kind = event.get("kind")
        if kind == "position_update":
            await self.send_json({
                "type": "position_update",
                "lat": event.get("lat"),
                "lng": event.get("lng"),
                "status": event.get("status"),
                "ts": event.get("ts"),
            })
            return
        if kind == "status":
            await self.send_json({"type": "status", "status": event.get("status")})
            return

    async def status_update(self, event):
        # Emitted by post_save signal via group_send type="status.update"
        payload = {
            "type": "status_update",
            "id": event.get("id"),
            "status": event.get("status"),
            "assigned_at": event.get("assigned_at"),
            "picked_up_at": event.get("picked_up_at"),
            "delivered_at": event.get("delivered_at"),
        }
        await self.send_json(payload)

    # Back-compat for older senders using type="tracker.update"
    async def tracker_update(self, event):
        data = event.get("data", {})
        await self.send_json({"type": "position_update", **data})

    # Back-compat for staff debug sender using type="broadcast"
    async def broadcast(self, event):
        payload = event.get("payload") or {}
        await self.send_json(payload)

    # -------------------- helpers --------------------
    @staticmethod
    def _haversine_m(a, b):
        (lat1, lng1), (lat2, lng2) = a, b
        R = 6371000.0
        dLat = math.radians(lat2 - lat1)
        dLng = math.radians(lng2 - lng1)
        s1 = math.sin(dLat/2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLng/2) ** 2
        return 2 * R * math.asin(math.sqrt(s1))

    @database_sync_to_async
    def _is_owner_driver(self, delivery_id: int, user_id: int) -> bool:
        try:
            Delivery = apps.get_model("orders", "Delivery")
            return Delivery.objects.filter(pk=int(delivery_id), driver_id=user_id).exists()
        except Exception:
            return False

    @database_sync_to_async
    def _can_subscribe(self, delivery_id: int, user_id: int) -> bool:
        Delivery = apps.get_model("orders", "Delivery")
        try:
            d = Delivery.objects.select_related("order").get(pk=int(delivery_id))
        except Delivery.DoesNotExist:
            return False
        return (d.driver_id == user_id) or (getattr(d.order, "user_id", None) == user_id)

    @database_sync_to_async
    def _save_position(self, delivery_id: int, user_id: int, lat: Decimal, lng: Decimal):
        """Persist position; returns (changed: bool, new_status: str|None)."""
        Delivery = apps.get_model("orders", "Delivery")
        DeliveryPing = apps.get_model("orders", "DeliveryPing")
        try:
            d = Delivery.objects.get(pk=int(delivery_id), driver_id=user_id)
        except Delivery.DoesNotExist:
            return False, None

        changed = False
        now = timezone.now()
        if d.last_lat != lat or d.last_lng != lng:
            d.last_lat = lat
            d.last_lng = lng
            changed = True
        d.last_ping_at = now

        new_status = None
        try:
            Status = Delivery.Status
            if d.status == Status.ASSIGNED:
                d.status = Status.EN_ROUTE
                new_status = d.status
        except Exception:
            pass

        fields = ["last_lat", "last_lng", "last_ping_at", "updated_at"]
        if new_status is not None:
            fields.append("status")
        d.save(update_fields=fields)

        if changed:
            try:
                DeliveryPing.objects.create(delivery=d, lat=lat, lng=lng)
            except Exception:
                pass
            # best-effort audit trail
            try:
                DeliveryEvent = apps.get_model("orders", "DeliveryEvent")
                DeliveryEvent.objects.create(
                    delivery=d, actor_id=user_id, type="position",
                    note={"lat": float(lat), "lng": float(lng)}
                )
            except Exception:
                pass

        return changed, new_status

    @database_sync_to_async
    def _update_status(self, delivery_id: int, user_id: int, status_new: str) -> bool:
        Delivery = apps.get_model("orders", "Delivery")
        try:
            d = Delivery.objects.get(pk=int(delivery_id), driver_id=user_id)
        except Delivery.DoesNotExist:
            return False

        if status_new not in {Delivery.Status.PICKED_UP, Delivery.Status.EN_ROUTE, Delivery.Status.DELIVERED}:
            return False

        d.status = status_new
        if status_new == Delivery.Status.PICKED_UP:
            d.picked_up_at = timezone.now()
        if status_new == Delivery.Status.DELIVERED:
            d.delivered_at = timezone.now()
        d.save(update_fields=["status", "picked_up_at", "delivered_at", "updated_at"])
        return True

    async def _handle_position_update(self, content):
        lat_raw = content.get("lat")
        lng_raw = content.get("lng")

        # Always broadcast for live UX, even if we later drop persistence
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "delivery.event", "kind": "position_update", "lat": lat_raw, "lng": lng_raw},
        )

        # Persist only if sender is assigned driver
        if not await self._is_owner_driver(self.delivery_id, self.user_id):
            await self.send_json({"type": "error", "error": "forbidden"})
            return

        try:
            lat_d = Decimal(str(lat_raw)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            lng_d = Decimal(str(lng_raw)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            await self.send_json({"type": "error", "error": "invalid_payload"})
            return

        if not (Decimal("-90") <= lat_d <= Decimal("90") and Decimal("-180") <= lng_d <= Decimal("180")):
            await self.send_json({"type": "error", "error": "out_of_range"})
            return

        # Global throttle per (driver, delivery) by 5s
        cache_key = f"ws:last:{self.user_id}:{self.delivery_id}"
        last = cache.get(cache_key)
        now_ms = int(timezone.now().timestamp() * 1000)
        if last and (now_ms - int(last)) < 5000:
            return
        cache.set(cache_key, now_ms, timeout=30)

        # Connection throttle: 8s and moved 25m
        due = (now_ms - self._last_saved_at_ms) >= 8000
        moved_enough = True
        lat_f, lng_f = float(lat_d), float(lng_d)
        if self._last_saved_ll is not None:
            moved_enough = self._haversine_m(self._last_saved_ll, (lat_f, lng_f)) >= 25.0

        if due and moved_enough:
            changed, new_status = await self._save_position(self.delivery_id, self.user_id, lat_d, lng_d)
            if changed:
                self._last_saved_at_ms = now_ms
                self._last_saved_ll = (lat_f, lng_f)
            if new_status is not None:
                await self.channel_layer.group_send(
                    self.group_name,
                    {"type": "delivery.event", "kind": "status", "status": new_status},
                )

    async def _handle_status_broadcast(self, content):
        status_new = content.get("status")
        if not isinstance(status_new, str) or not status_new:
            return
        if not await self._is_owner_driver(self.delivery_id, self.user_id):
            await self.send_json({"type": "error", "error": "forbidden"})
            return
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "delivery.event", "kind": "status", "status": status_new},
        )


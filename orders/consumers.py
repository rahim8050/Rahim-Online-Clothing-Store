from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math

from .models import Delivery, DeliveryPing

class DeliveryTrackerConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.delivery_id = self.scope["url_route"]["kwargs"]["delivery_id"]
        # Align with Delivery.ws_group (e.g., "delivery.123")
        self.group_name = f"delivery.{self.delivery_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # per-connection throttle state
        self._last_saved_at = 0
        self._last_saved_ll = None  # (lat, lng) floats

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    # Allow manual test from browser: ws.send(JSON.stringify({...}))
    async def receive_json(self, content, **kwargs):
        """
        Accept both legacy and current payload shapes and broadcast to the group:
        - {"type":"position_update", "lat": ..., "lng": ...}
        - {"op":"update", "lat": ..., "lng": ..., "status": "..."}
        - {"type":"status", "status": "picked_up"}
        - {"op":"ping"}
        """
        msg_type = content.get("type") or content.get("op")

        if msg_type in ("position_update", "update", "position"):
            lat_raw = content.get("lat")
            lng_raw = content.get("lng")

            # Always broadcast for live UX, even if we later drop persistence
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "delivery.event",
                    "kind": "position_update",
                    "lat": lat_raw,
                    "lng": lng_raw,
                },
            )

            # Persist only if the sender is the assigned driver and payload is valid
            user = self.scope.get("user")
            if not getattr(user, "is_authenticated", False):
                return

            if not await self._is_owner_driver(self.delivery_id, user.id):
                # Optional: inform the sender only
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

            # Throttle DB writes per connection
            now_ms = int(timezone.now().timestamp() * 1000)
            due = (now_ms - self._last_saved_at) >= 8000  # 8s
            moved_enough = True
            lat_f, lng_f = float(lat_d), float(lng_d)
            if self._last_saved_ll is not None:
                moved_enough = self._haversine_m(self._last_saved_ll, (lat_f, lng_f)) >= 25.0

            if due and moved_enough:
                changed, new_status = await self._save_position(self.delivery_id, user.id, lat_d, lng_d)
                if changed:
                    self._last_saved_at = now_ms
                    self._last_saved_ll = (lat_f, lng_f)
                # If status auto-progressed, broadcast status
                if new_status is not None:
                    await self.channel_layer.group_send(
                        self.group_name,
                        {"type": "delivery.event", "kind": "status", "status": new_status},
                    )
            return

        if msg_type == "status":
            # Only drivers can set status
            user = self.scope.get("user")
            if not getattr(user, "is_authenticated", False):
                return
            status_new = content.get("status")
            ok = await self._update_status(self.delivery_id, user.id, status_new)
            if ok:
                await self.channel_layer.group_send(
                    self.group_name,
                    {"type": "delivery.event", "kind": "status", "status": status_new},
                )
            return

        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return

    # Canonical group event -> fan out to clients in the expected shape
    async def delivery_event(self, event):
        kind = event.get("kind")
        if kind == "position_update":
            await self.send_json(
                {
                    "type": "position_update",
                    "lat": event.get("lat"),
                    "lng": event.get("lng"),
                    # optional passthroughs
                    "status": event.get("status"),
                    "ts": event.get("ts"),
                }
            )
            return

        if kind == "status":
            await self.send_json({"type": "status", "status": event.get("status")})
            return

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
    def _is_owner_driver(self, delivery_id: int | str, user_id: int) -> bool:
        try:
            return Delivery.objects.filter(pk=int(delivery_id), driver_id=user_id).exists()
        except Exception:
            return False

    @database_sync_to_async
    def _save_position(self, delivery_id: int | str, user_id: int, lat: Decimal, lng: Decimal):
        """
        Persist position for the assigned driver. Returns (changed: bool, new_status: str|None)
        """
        try:
            d = Delivery.objects.get(pk=int(delivery_id), driver_id=user_id)
        except Delivery.DoesNotExist:
            return False, None

        changed = False
        new_status = None
        now = timezone.now()
        # Only consider changed if moved
        if d.last_lat != lat or d.last_lng != lng:
            d.last_lat = lat
            d.last_lng = lng
            changed = True
        d.last_ping_at = now

        if d.status == Delivery.Status.ASSIGNED:
            d.status = Delivery.Status.EN_ROUTE
            new_status = d.status

        fields = ["last_lat", "last_lng", "last_ping_at", "updated_at"]
        if new_status:
            fields.append("status")
        d.save(update_fields=fields)
        # Store history point when changed
        if changed:
            try:
                DeliveryPing.objects.create(delivery=d, lat=lat, lng=lng)
            except Exception:
                pass
        return changed, new_status

    @database_sync_to_async
    def _update_status(self, delivery_id: int | str, user_id: int, status_new: str) -> bool:
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

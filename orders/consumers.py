<<<<<<< HEAD
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
=======
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.core.cache import cache
from django.apps import apps
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math

class DeliveryTrackerConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return
        self.delivery_id = int(self.scope["url_route"]["kwargs"]["delivery_id"])
        # Allow both the assigned driver and the order owner to subscribe (view-only for owner)
        if not await self._can_subscribe(self.delivery_id, user.id):
            await self.close()
            return
        self.group_name = f"delivery.{self.delivery_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # per-connection throttle state (for DB writes)
        self._last_saved_at = 0
        self._last_saved_ll = None  # (lat, lng) floats

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass
>>>>>>> development

    # Allow manual test from browser: ws.send(JSON.stringify({...}))
    async def receive_json(self, content, **kwargs):
<<<<<<< HEAD
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
=======
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

            # Throttle incoming WS globally per (driver, delivery) by 5s (cache)
            cache_key = f"ws:last:{user.id}:{self.delivery_id}"
            last = cache.get(cache_key)
            now_ms = int(timezone.now().timestamp() * 1000)
            if last and (now_ms - int(last)) < 5000:
                return
            cache.set(cache_key, now_ms, timeout=30)

            # Additional per-connection throttle for DB writes
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
            # WS status does not mutate DB — only broadcast as a hint to UIs
            status_new = content.get("status")
            if isinstance(status_new, str) and status_new:
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
    def _is_owner_driver(self, delivery_id: int | str, user_id: int) -> bool:
        try:
            Delivery = apps.get_model("orders", "Delivery")
            return Delivery.objects.filter(pk=int(delivery_id), driver_id=user_id).exists()
        except Exception:
            return False

    @database_sync_to_async
    def _can_subscribe(self, delivery_id: int | str, user_id: int) -> bool:
        Delivery = apps.get_model("orders", "Delivery")
        try:
            d = Delivery.objects.select_related("order").get(pk=int(delivery_id))
        except Delivery.DoesNotExist:
            return False
        return (d.driver_id == user_id) or (getattr(d.order, "user_id", None) == user_id)

    @database_sync_to_async
    def _save_position(self, delivery_id: int | str, user_id: int, lat: Decimal, lng: Decimal):
        """
        Persist position for the assigned driver. Returns (changed: bool, new_status: str|None)
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
            # best-effort audit
            try:
                DeliveryEvent = apps.get_model("orders", "DeliveryEvent")
                DeliveryEvent.objects.create(delivery=d, actor_id=user_id, type="position", note={"lat": float(lat), "lng": float(lng)})
            except Exception:
                pass
        return changed, new_status

    @database_sync_to_async
    def _update_status(self, delivery_id: int | str, user_id: int, status_new: str) -> bool:
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
>>>>>>> development
# orders/consumers.py
import math
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.apps import apps
from django.core.cache import cache
from django.utils import timezone

Q6 = Decimal("0.000001")
CACHE_WS_THROTTLE_SEC = 5          # global per (driver, delivery)
CONN_WRITE_THROTTLE_MS = 8000      # per-connection DB write throttle
CONN_MIN_MOVE_M = 25.0             # min movement to record


class DeliveryConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket room per delivery:
      - Group name: delivery.<id>
      - Allowed subscribers: assigned driver OR order owner
      - Only the assigned driver may persist position/status
    """

    async def connect(self):
        user = self.scope.get("user")
        if not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return

        try:
            self.delivery_id = int(self.scope["url_route"]["kwargs"]["delivery_id"])
        except Exception:
            await self.close(code=4400)
            return

        if not await self._can_subscribe(self.delivery_id, user.id):
            await self.close(code=4403)
            return

        self.user_id = user.id
        self.group_name = f"delivery.{self.delivery_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Per-connection throttle state
        self._last_saved_at_ms = 0
        self._last_saved_ll = None  # (lat, lng) floats

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    # ----- Receiving messages from client -----
    async def receive_json(self, content, **kwargs):
        """
        Accept legacy/current payloads:
          - {"type":"position_update", "lat": ..., "lng": ...}
          - {"op":"update", "lat": ..., "lng": ...}
          - {"type":"status", "status": "picked_up" | "en_route" | "delivered"}
          - {"op":"ping"}
        """
        msg_type = content.get("type") or content.get("op")

        if msg_type in ("position_update", "update", "position"):
            await self._handle_position(content)
            return

        if msg_type == "status":
            await self._handle_status_broadcast(content)
            return

        if msg_type == "ping":
            await self.send_json({"type": "pong"})
            return

        await self.send_json({"type": "error", "error": "unsupported_type"})

    # ----- Group events -> client fanout -----
    async def delivery_event(self, event):
        """Canonical group event."""
        kind = event.get("kind")
        if kind == "position_update":
            await self.send_json({
                "type": "position_update",
                "lat": event.get("lat"),
                "lng": event.get("lng"),
                "ts": event.get("ts"),
            })
        elif kind == "status":
            await self.send_json({"type": "status", "status": event.get("status")})

    # Back-compat: server sends type="status.update"
    async def status_update(self, event):
        await self.send_json({
            "type": "status_update",
            "id": event.get("id"),
            "status": event.get("status"),
            "assigned_at": event.get("assigned_at"),
            "picked_up_at": event.get("picked_up_at"),
            "delivered_at": event.get("delivered_at"),
        })

    # Back-compat: older senders
    async def tracker_update(self, event):
        data = event.get("data", {})
        await self.send_json({"type": "position_update", **data})

    # Back-compat: staff debug pathway
    async def broadcast(self, event):
        payload = event.get("payload") or {}
        await self.send_json(payload)

    # ----- Handlers -----
    async def _handle_position(self, content):
        lat_raw = content.get("lat")
        lng_raw = content.get("lng")

        # Always broadcast for live UX (even if we later reject persistence).
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "delivery.event", "kind": "position_update", "lat": lat_raw, "lng": lng_raw, "ts": timezone.now().isoformat()},
        )

        # Persist only if sender is the assigned driver and payload is valid
        if not await self._is_driver(self.delivery_id, self.user_id):
            await self.send_json({"type": "error", "error": "forbidden"})
            return

        try:
            lat_d = Decimal(str(lat_raw)).quantize(Q6, rounding=ROUND_HALF_UP)
            lng_d = Decimal(str(lng_raw)).quantize(Q6, rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            await self.send_json({"type": "error", "error": "invalid_payload"})
            return

        if not (Decimal("-90") <= lat_d <= Decimal("90") and Decimal("-180") <= lng_d <= Decimal("180")):
            await self.send_json({"type": "error", "error": "out_of_range"})
            return

        # Global cache throttle per (driver, delivery)
        cache_key = f"ws:last:{self.user_id}:{self.delivery_id}"
        last = cache.get(cache_key)
        now_ms = int(timezone.now().timestamp() * 1000)
        if last and (now_ms - int(last)) < CACHE_WS_THROTTLE_SEC * 1000:
            return
        cache.set(cache_key, now_ms, timeout=CACHE_WS_THROTTLE_SEC + 5)

        # Per-connection throttle & minimal movement
        due = (now_ms - self._last_saved_at_ms) >= CONN_WRITE_THROTTLE_MS
        lat_f, lng_f = float(lat_d), float(lng_d)
        moved_enough = True
        if self._last_saved_ll is not None:
            moved_enough = self._haversine_m(self._last_saved_ll, (lat_f, lng_f)) >= CONN_MIN_MOVE_M

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
        """Broadcast status as a hint. Only driver is allowed to originate."""
        status_new = content.get("status")
        if not isinstance(status_new, str) or not status_new:
            return
        if not await self._is_driver(self.delivery_id, self.user_id):
            await self.send_json({"type": "error", "error": "forbidden"})
            return
        # Optionally persist (enable if you want WS to mutate DB):
        # ok = await self._update_status(self.delivery_id, self.user_id, status_new)
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "delivery.event", "kind": "status", "status": status_new},
        )

    # ----- Helpers -----
    @staticmethod
    def _haversine_m(a, b):
        (lat1, lng1), (lat2, lng2) = a, b
        R = 6371000.0
        dLat = math.radians(lat2 - lat1)
        dLng = math.radians(lng2 - lng1)
        s1 = math.sin(dLat/2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLng/2) ** 2
        return 2 * R * math.asin(math.sqrt(s1))

    @database_sync_to_async
    def _can_subscribe(self, delivery_id: int, user_id: int) -> bool:
        Delivery = apps.get_model("orders", "Delivery")
        try:
            d = Delivery.objects.select_related("order").get(pk=int(delivery_id))
        except Delivery.DoesNotExist:
            return False
        return (d.driver_id == user_id) or (getattr(d.order, "user_id", None) == user_id)

    @database_sync_to_async
    def _is_driver(self, delivery_id: int, user_id: int) -> bool:
        Delivery = apps.get_model("orders", "Delivery")
        return Delivery.objects.filter(pk=int(delivery_id), driver_id=user_id).exists()

    @database_sync_to_async
    def _save_position(self, delivery_id: int, user_id: int, lat: Decimal, lng: Decimal):
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
        now = timezone.now()
        if d.last_lat != lat or d.last_lng != lng:
            d.last_lat = lat
            d.last_lng = lng
            changed = True
        d.last_ping_at = now

        new_status = None
        # Auto-progress ASSIGNED → EN_ROUTE on first movement
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
        valid = {getattr(Delivery.Status, "PICKED_UP", "picked_up"),
                 getattr(Delivery.Status, "EN_ROUTE", "en_route"),
                 getattr(Delivery.Status, "DELIVERED", "delivered")}
        if status_new not in valid:
            return False
        d.status = status_new
        if status_new == getattr(Delivery.Status, "PICKED_UP", "picked_up"):
            d.picked_up_at = timezone.now()
        if status_new == getattr(Delivery.Status, "DELIVERED", "delivered"):
            d.delivered_at = timezone.now()
        d.save(update_fields=["status", "picked_up_at", "delivered_at", "updated_at"])
        return True

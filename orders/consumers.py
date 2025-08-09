"""WebSocket consumers for order delivery tracking."""

import asyncio
import logging
from typing import Optional

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Order, OrderItem
from .ws_codes import WSErr

logger = logging.getLogger("orders.ws")


class DeliveryTrackerConsumer(AsyncJsonWebsocketConsumer):
    """
    Simulate live delivery tracking for a single OrderItem.
    Open the socket at: /ws/track/<order_id>/<item_id>/
    """

    STEPS = 60
    TICK_DELAY = 0.5  # seconds

    # -------------------------
    # Lifecycle
    # -------------------------

    async def connect(self):
        """
        Accept the connection first so we can send structured errors to the client
        instead of failing the handshake (which shows up as 1006 in the browser).
        """
        # Parse URL kwargs (don’t crash if missing)
        self.order_id: Optional[int] = None
        self.item_id: Optional[int] = None
        self._runner_task: Optional[asyncio.Task] = None

        try:
            self.order_id = int(self.scope["url_route"]["kwargs"].get("order_id"))
            self.item_id = int(self.scope["url_route"]["kwargs"].get("item_id"))
        except Exception:
            await self.accept()
            await self._fail(4000, "bad_url_params")
            return

        # Accept early
        await self.accept()
        # Kick off the simulation as a background task
        self._runner_task = asyncio.create_task(self._run_simulation())

    async def disconnect(self, close_code):
        # Cancel background simulation if still running
        if self._runner_task and not self._runner_task.done():
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass
        logger.debug("WS disconnected with code %s", close_code)

    async def receive_json(self, content, **kwargs):
        """
        Keep a lightweight handler for client messages.
        - {type:"ping"} -> {type:"pong"}
        - echo everything else for testing
        """
        t = content.get("type")
        if t == "ping":
            await self.send_json({"type": "pong"})
            return
        await self.send_json({"type": "echo", "data": content})

    # -------------------------
    # Simulation Runner
    # -------------------------

    async def _run_simulation(self):
        """
        Validate inputs, load data, and stream ticks.
        Runs in a background task so connect() can return immediately.
        """
        try:
            # Load and validate
            user = self.scope.get("user")
            if not user or not user.is_authenticated:
                await self._fail(WSErr.FORBIDDEN, "forbidden")
                return

            order = await self._get_order(self.order_id)
            if not order:
                await self._fail(WSErr.ORDER_NOT_FOUND, "order_not_found")
                return

            if order.user_id != user.id:
                await self._fail(WSErr.FORBIDDEN, "forbidden")
                return

            item = await self._get_item(self.item_id)
            if not item or item.order_id != order.id:
                await self._fail(WSErr.ITEM_NOT_FOUND, "item_not_found")
                return

            if not item.warehouse_id:
                await self._fail(WSErr.WAREHOUSE_MISSING, "warehouse_missing")
                return

            start_lat = item.warehouse.latitude
            start_lng = item.warehouse.longitude
            end_lat = order.latitude
            end_lng = order.longitude

            if end_lat is None or end_lng is None:
                await self._fail(WSErr.DEST_COORDS_MISSING, "destination_missing")
                return

            # Status gates
            if item.delivery_status == "delivered":
                await self.send_json({
                    "type": "complete",
                    "lat": end_lat, "lng": end_lng,
                    "latitude": end_lat, "longitude": end_lng,
                    "status": "delivered",
                })
                await self.close()
                return

            if item.delivery_status not in {"dispatched", "en_route"}:
                await self._fail(4004, f"not_dispatched (got {item.delivery_status})")
                return

            if item.delivery_status == "dispatched":
                await self._set_status(item.pk, "en_route")

            # Initial payload
            await self.send_json({
                "type": "init",
                "warehouse": {
                    "lat": start_lat, "lng": start_lng,
                    "latitude": start_lat, "longitude": start_lng,
                },
                "destination": {
                    "lat": end_lat, "lng": end_lng,
                    "latitude": end_lat, "longitude": end_lng,
                },
                "status": "en_route",
            })

            # Straight-line simulator
            lat_step = (end_lat - start_lat) / self.STEPS
            lng_step = (end_lng - start_lng) / self.STEPS

            for i in range(1, self.STEPS + 1):
                lat = start_lat + lat_step * i
                lng = start_lng + lng_step * i
                status = "nearby" if i > self.STEPS * 0.9 else "en_route"

                await self.send_json({
                    "type": "tick",
                    "lat": lat, "lng": lng,
                    "latitude": lat, "longitude": lng,
                    "status": status,
                    "progress": round(i * 100 / self.STEPS, 2),
                })

                # yield control; if client disconnects this will raise CancelledError quickly
                await asyncio.sleep(self.TICK_DELAY)

            # Mark delivered and send final
            await self._set_status(item.pk, "delivered")
            await self.send_json({
                "type": "complete",
                "lat": end_lat, "lng": end_lng,
                "latitude": end_lat, "longitude": end_lng,
                "status": "delivered",
            })
            await self.close()

        except asyncio.CancelledError:
            # Normal path when the client disconnects mid-stream
            logger.debug("Simulation cancelled (client disconnected) order=%s item=%s", self.order_id, self.item_id)
            raise
        except Exception as exc:
            logger.exception("Simulation crashed: %s", exc)
            try:
                await self.send_json({"type": "error", "message": "server_error"})
            finally:
                await self.close(code=1011)

    # -------------------------
    # Helpers
    # -------------------------

    async def _fail(self, code: int, message: str):
        """
        Send an error payload then close the socket with `code`.
        Codes 4000-4999 are application-defined close codes.
        """
        await self.send_json({
            "type": "error",
            "code": code,
            "message": message,
            "order_id": self.order_id,
            "item_id": self.item_id,
        })
        await self.close(code=code)

    # -------------------------
    # DB helpers (thread off)
    # -------------------------

    @database_sync_to_async
    def _get_order(self, order_id: int):
        try:
            return Order.objects.only("id", "user_id", "latitude", "longitude").get(pk=order_id)
        except Order.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_item(self, item_id: int):
        try:
            return (
                OrderItem.objects
                .select_related("warehouse", "order")
                .only(
                    "id",
                    "order_id",
                    "warehouse_id",
                    "delivery_status",
                    "warehouse__latitude",
                    "warehouse__longitude",
                    "order__id",
                    "order__user_id",
                    "order__latitude",
                    "order__longitude",
                )
                .get(pk=item_id)
            )
        except OrderItem.DoesNotExist:
            return None

    @database_sync_to_async
    def _set_status(self, item_pk: int, status: str):
        """
        Update status safely inside the DB thread. We refetch by pk to avoid
        sharing ORM instances across threads.
        """
        try:
            obj = OrderItem.objects.get(pk=item_pk)
            obj.delivery_status = status
            obj.save(update_fields=["delivery_status"])
        except OrderItem.DoesNotExist:
            # If it vanished mid-stream, just log it; the WS will already be open.
            logger.warning("Item %s disappeared while setting status=%s", item_pk, status)

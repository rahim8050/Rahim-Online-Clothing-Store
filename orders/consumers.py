"""WebSocket consumers for order delivery tracking."""

import asyncio
import traceback

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Order, OrderItem


class DeliveryTrackerConsumer(AsyncJsonWebsocketConsumer):
    """Simulate live delivery tracking for a single ``OrderItem``."""

    STEPS = 60
    TICK_DELAY = 0.5  # seconds

    async def _fail(self, code: int, message: str):
        """Send an error payload then close the socket with ``code``."""
        await self.send_json({"type": "error", "code": code, "message": message})
        await self.close(code=code)

    async def connect(self):
        try:
            self.order_id = int(self.scope["url_route"]["kwargs"]["order_id"])
            self.item_id = int(self.scope["url_route"]["kwargs"]["item_id"])
            await self.accept()  # accept early to avoid client-side errors

            self.order = await self.get_order(self.order_id)
            if not self.order:
                return await self._fail(4000, "order_not_found")

            self.item = await self.get_item(self.item_id)
            if not self.item:
                return await self._fail(4001, "item_not_found")

            if not self.item.warehouse:
                return await self._fail(4002, "warehouse_missing")

            start_lat = self.item.warehouse.latitude
            start_lng = self.item.warehouse.longitude
            end_lat = self.order.latitude
            end_lng = self.order.longitude

            if None in (start_lat, start_lng, end_lat, end_lng):
                return await self._fail(4005, "coords_missing")

            if self.item.delivery_status == "delivered":
                await self.send_json(
                    {
                        "type": "complete",
                        "latitude": end_lat,
                        "longitude": end_lng,
                        "status": "delivered",
                    }
                )
                return await self.close()

            if self.item.delivery_status not in {"dispatched", "en_route"}:
                return await self._fail(
                    4004, f"not_dispatched (got {self.item.delivery_status})"
                )

            await self.set_status("en_route")
            await self.send_json(
                {
                    "type": "init",
                    "warehouse": {"latitude": start_lat, "longitude": start_lng},
                    "destination": {"latitude": end_lat, "longitude": end_lng},
                    "status": "en_route",
                }
            )

            lat_step = (end_lat - start_lat) / self.STEPS
            lng_step = (end_lng - start_lng) / self.STEPS
            for i in range(1, self.STEPS + 1):
                lat = start_lat + lat_step * i
                lng = start_lng + lng_step * i
                status = "nearby" if i > self.STEPS * 0.9 else "en_route"
                await self.send_json(
                    {
                        "type": "tick",
                        "latitude": lat,
                        "longitude": lng,
                        "status": status,
                    }
                )
                await asyncio.sleep(self.TICK_DELAY)

            await self.set_status("delivered")
            await self.send_json(
                {
                    "type": "complete",
                    "latitude": end_lat,
                    "longitude": end_lng,
                    "status": "delivered",
                }
            )
            await self.close()

        except Exception:  # pragma: no cover - defensive programming
            traceback.print_exc()
            try:
                await self.send_json({"type": "error", "message": "server_error"})
            finally:
                await self.close(code=1011)

    async def receive_json(self, content, **kwargs):
        """Echo any received payload back to the client."""
        await self.send_json({"type": "echo", "data": content})

    @database_sync_to_async
    def get_order(self, order_id: int):
        try:
            return Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return None

    @database_sync_to_async
    def get_item(self, item_id: int):
        try:
            return OrderItem.objects.select_related("warehouse").get(pk=item_id)
        except OrderItem.DoesNotExist:
            return None

    @database_sync_to_async
    def set_status(self, status: str):
        self.item.delivery_status = status
        self.item.save(update_fields=["delivery_status"])


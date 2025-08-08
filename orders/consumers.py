# orders/consumers.py
import asyncio
import traceback
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Order, OrderItem

class DeliveryTrackerConsumer(AsyncJsonWebsocketConsumer):
    STEPS = 60
    TICK_DELAY = 0.5

    async def connect(self):
        try:
            self.order_id = int(self.scope["url_route"]["kwargs"]["order_id"])
            self.item_id  = int(self.scope["url_route"]["kwargs"]["item_id"])

            # ACCEPT ASAP so failures don’t look like "REJECT"
            await self.accept()
            await self.send_json({"type": "hello", "order_id": self.order_id, "item_id": self.item_id})

            self.order = await self.get_order(self.order_id)
            self.item  = await self.get_item(self.item_id)

            if not self.order:
                await self.send_json({"type": "error", "message": "order_not_found"})
                return await self.close(code=4000)

            if not self.item:
                await self.send_json({"type": "error", "message": "item_not_found"})
                return await self.close(code=4001)

            if not getattr(self.item, "warehouse", None):
                await self.send_json({"type": "error", "message": "warehouse_missing"})
                return await self.close(code=4002)

            start_lat = self.item.warehouse.latitude
            start_lng = self.item.warehouse.longitude
            end_lat   = self.order.latitude
            end_lng   = self.order.longitude

            # validate coords are numbers
            for v in (start_lat, start_lng, end_lat, end_lng):
                if v is None:
                    await self.send_json({"type": "error", "message": "bad_coordinates"})
                    return await self.close(code=4003)

            # If already delivered, just finish
            if self.item.delivery_status == "delivered":
                await self.send_json({
                    "type": "complete",
                    "latitude": end_lat,
                    "longitude": end_lng,
                    "status": "delivered",
                })
                return await self.close()

            # Only block tracking if you really need to
            if self.item.delivery_status not in {"dispatched", "en_route"}:
                await self.send_json({"type": "error", "message": "not_dispatched"})
                return await self.close(code=4004)

            await self.set_status("en_route")
            await self.send_json({
                "type": "init",
                "warehouse": {"latitude": start_lat, "longitude": start_lng},
                "destination": {"latitude": end_lat, "longitude": end_lng},
                "status": "en_route",
            })

            lat_step = (end_lat - start_lat) / self.STEPS
            lng_step = (end_lng - start_lng) / self.STEPS

            for i in range(1, self.STEPS + 1):
                lat = start_lat + lat_step * i
                lng = start_lng + lng_step * i
                status = "nearby" if i > self.STEPS * 0.9 else "en_route"
                await self.send_json({"type": "tick", "latitude": lat, "longitude": lng, "status": status})
                await asyncio.sleep(self.TICK_DELAY)

            await self.set_status("delivered")
            await self.send_json({"type": "complete", "latitude": end_lat, "longitude": end_lng, "status": "delivered"})
            await self.close()

        except Exception as e:
            print("WS CONNECT ERROR:", repr(e))
            traceback.print_exc()
            try:
                await self.send_json({"type": "error", "message": "server_error"})
            finally:
                await self.close(code=1011)

    async def receive_json(self, content, **kwargs):
        # optional: handle pings or client messages
        await self.send_json({"type": "echo", "data": content})

    @database_sync_to_async
    def get_order(self, order_id):
        try:
            return Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return None

    @database_sync_to_async
    def get_item(self, item_id):
        try:
            return OrderItem.objects.select_related("warehouse").get(pk=item_id)
        except OrderItem.DoesNotExist:
            return None

    @database_sync_to_async
    def set_status(self, status):
        self.item.delivery_status = status
        self.item.save(update_fields=["delivery_status"])

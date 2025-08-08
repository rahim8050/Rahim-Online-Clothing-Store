import asyncio
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Order, OrderItem


class DeliveryTrackerConsumer(AsyncJsonWebsocketConsumer):
    STEPS = 60
    TICK_DELAY = 0.5

    async def connect(self):
        self.order_id = self.scope["url_route"]["kwargs"]["order_id"]
        self.item_id = self.scope["url_route"]["kwargs"]["item_id"]

        self.order = await self.get_order(self.order_id)
        self.item = await self.get_item(self.item_id)

        if not self.order or not self.item or not self.item.warehouse:
            await self.close()
            return

        start_lat = self.item.warehouse.latitude
        start_lng = self.item.warehouse.longitude
        end_lat = self.order.latitude
        end_lng = self.order.longitude

        await self.accept()

        if self.item.delivery_status == "delivered":
            await self.send_json(
                {
                    "type": "complete",
                    "latitude": end_lat,
                    "longitude": end_lng,
                    "status": "delivered",
                }
            )
            await self.close()
            return

        if self.item.delivery_status != "dispatched":
            await self.close()
            return

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
            status = "en_route"
            if i > self.STEPS * 0.9:
                status = "nearby"
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

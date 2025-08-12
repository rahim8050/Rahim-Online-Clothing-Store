import asyncio

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase

from Rahim_Online_ClothesStore.asgi import application
from orders.models import Delivery, Order, OrderItem
from product_app.models import Category, Product, Warehouse


class DeliveryConsumerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="p")
        self.driver = User.objects.create_user(username="driver", password="p")
        self.other = User.objects.create_user(username="other", password="p")
        cat = Category.objects.create(name="c", slug="c")
        prod = Product.objects.create(category=cat, name="p", slug="p", price=10)
        wh = Warehouse.objects.create(name="w", latitude=0, longitude=0)
        order = Order.objects.create(
            user=self.owner,
            full_name="F",
            email="e@e.com",
            address="A",
            dest_address_text="d",
            dest_lat=1,
            dest_lng=2,
        )
        OrderItem.objects.create(order=order, product=prod, price=10, quantity=1, warehouse=wh)
        delivery = Delivery(order=order)
        delivery.snapshot_endpoints_from_order()
        delivery.save()
        self.delivery = delivery

    def test_snapshot_sets_dest(self):
        self.assertEqual(self.delivery.dest_lat, self.delivery.order.dest_lat)
        self.assertEqual(self.delivery.dest_lng, self.delivery.order.dest_lng)
        item = self.delivery.order.items.first()
        self.assertEqual(self.delivery.origin_lat, item.warehouse.latitude)
        self.assertEqual(self.delivery.origin_lng, item.warehouse.longitude)

    def test_consumer_denies_intruder(self):
        async def flow():
            comm = WebsocketCommunicator(application, f"/ws/deliveries/{self.delivery.id}/")
            comm.scope["user"] = self.other
            connected, _ = await comm.connect()
            if connected:
                await comm.receive_nothing()
                code = await comm.wait_closed()
            else:
                code = comm.close_code
            return code
        code = async_to_sync(flow)()
        self.assertEqual(code, 4003)

    def test_driver_ping_updates(self):
        self.delivery.driver = self.driver
        self.delivery.save(update_fields=["driver"])

        async def flow():
            comm = WebsocketCommunicator(application, f"/ws/deliveries/{self.delivery.id}/")
            comm.scope["user"] = self.driver
            connected, _ = await comm.connect()
            assert connected
            await comm.send_json_to({"type": "ping", "lat": 0, "lng": 0})
            await asyncio.sleep(2.1)
            await comm.send_json_to({"type": "ping", "lat": 1, "lng": 1})
            event = await comm.receive_json_from()
            await comm.disconnect()
            return event

        event = async_to_sync(flow)()
        self.assertEqual(event["event"], "position")
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.last_lat, 1)
        self.assertEqual(self.delivery.last_lng, 1)

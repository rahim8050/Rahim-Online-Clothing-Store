from django.test import TestCase
from django.contrib.auth import get_user_model
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator

from product_app.models import Category, Product, Warehouse, ProductStock
from .models import Order, OrderItem
from .services.assignment import assign_warehouses_and_update_stock
from .consumers import DeliveryTrackerConsumer
from Rahim_Online_ClothesStore.asgi import application


class AssignmentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p", email="u@example.com")
        self.category = Category.objects.create(name="c", slug="c")
        self.product = Product.objects.create(category=self.category, name="p", slug="p", price=10)
        self.wh = Warehouse.objects.create(name="W", latitude=0, longitude=0)
        ProductStock.objects.create(product=self.product, warehouse=self.wh, quantity=10)
        self.order = Order.objects.create(user=self.user, full_name="F", email="u@example.com", address="A")
        self.item = OrderItem.objects.create(order=self.order, product=self.product, price=10, quantity=2)

    def test_no_coords_no_assignment(self):
        assign_warehouses_and_update_stock(self.order)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.warehouse)

    def test_idempotent_assignment(self):
        self.order.latitude = 1
        self.order.longitude = 1
        self.order.save()
        assign_warehouses_and_update_stock(self.order)
        self.item.refresh_from_db()
        stock = ProductStock.objects.get(product=self.product, warehouse=self.wh)
        self.assertEqual(self.item.warehouse, self.wh)
        self.assertEqual(stock.quantity, 8)
        assign_warehouses_and_update_stock(self.order)
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 8)


class DeliveryTrackerConsumerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u2", password="p", email="u2@example.com")
        self.category = Category.objects.create(name="c2", slug="c2")
        self.product = Product.objects.create(category=self.category, name="p2", slug="p2", price=10)
        self.wh = Warehouse.objects.create(name="W2", latitude=0, longitude=0)
        self.order = Order.objects.create(user=self.user, full_name="F", email="u2@example.com", address="A", latitude=1, longitude=1)
        self.item = OrderItem.objects.create(order=self.order, product=self.product, price=10, quantity=1, warehouse=self.wh, delivery_status="dispatched")

    def test_full_flow(self):
        DeliveryTrackerConsumer.STEPS = 1
        DeliveryTrackerConsumer.TICK_DELAY = 0

        async def flow():
            communicator = WebsocketCommunicator(application, f"/ws/track/{self.order.id}/{self.item.id}/")
            connected, _ = await communicator.connect()
            assert connected
            init = await communicator.receive_json_from()
            tick = await communicator.receive_json_from()
            complete = await communicator.receive_json_from()
            await communicator.disconnect()
            return init, tick, complete

        init, tick, complete = async_to_sync(flow)()
        self.assertEqual(init["type"], "init")
        self.assertEqual(tick["type"], "tick")
        self.assertEqual(complete["type"], "complete")

    def test_reconnect_delivered(self):
        self.item.delivery_status = "delivered"
        self.item.save()

        async def flow():
            communicator = WebsocketCommunicator(application, f"/ws/track/{self.order.id}/{self.item.id}/")
            connected, _ = await communicator.connect()
            assert connected
            complete = await communicator.receive_json_from()
            await communicator.disconnect()
            return complete

        complete = async_to_sync(flow)()
        self.assertEqual(complete["type"], "complete")

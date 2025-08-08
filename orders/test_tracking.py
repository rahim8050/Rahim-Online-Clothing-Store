from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase

from Rahim_Online_ClothesStore.asgi import application
from orders.consumers import DeliveryTrackerConsumer
from orders.models import Order, OrderItem
from product_app.models import Category, Product, Warehouse


class DeliveryTrackerConsumerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p")
        self.category = Category.objects.create(name="c", slug="c")
        self.product = Product.objects.create(
            category=self.category, name="p", slug="p", price=10
        )
        self.wh = Warehouse.objects.create(name="W", latitude=0, longitude=0)

    def _make_item(self, status="dispatched", with_wh=True, with_coords=True):
        order_kwargs = dict(
            user=self.user,
            full_name="F",
            email="e@e.com",
            address="A",
        )
        if with_coords:
            order_kwargs.update(latitude=1, longitude=1)
        order = Order.objects.create(**order_kwargs)
        warehouse = self.wh if with_wh else None
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            price=10,
            quantity=1,
            warehouse=warehouse,
            delivery_status=status,
        )
        return order, item

    def test_flow(self):
        order, item = self._make_item()
        DeliveryTrackerConsumer.STEPS = 1
        DeliveryTrackerConsumer.TICK_DELAY = 0

        async def flow():
            communicator = WebsocketCommunicator(
                application, f"/ws/track/{order.id}/{item.id}/"
            )
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

    def test_missing_warehouse(self):
        order, item = self._make_item(with_wh=False)

        async def flow():
            communicator = WebsocketCommunicator(
                application, f"/ws/track/{order.id}/{item.id}/"
            )
            connected, _ = await communicator.connect()
            assert connected
            msg = await communicator.receive_json_from()
            await communicator.disconnect()
            return msg

        msg = async_to_sync(flow)()
        self.assertEqual(
            msg, {"type": "error", "code": 4002, "message": "warehouse_missing"}
        )

    def test_missing_order_coords(self):
        order, item = self._make_item(with_coords=False)

        async def flow():
            communicator = WebsocketCommunicator(
                application, f"/ws/track/{order.id}/{item.id}/"
            )
            connected, _ = await communicator.connect()
            assert connected
            msg = await communicator.receive_json_from()
            await communicator.disconnect()
            return msg

        msg = async_to_sync(flow)()
        self.assertEqual(msg, {"type": "error", "code": 4005, "message": "coords_missing"})

    def test_bad_status(self):
        order, item = self._make_item(status="created")

        async def flow():
            communicator = WebsocketCommunicator(
                application, f"/ws/track/{order.id}/{item.id}/"
            )
            connected, _ = await communicator.connect()
            assert connected
            msg = await communicator.receive_json_from()
            await communicator.disconnect()
            return msg

        msg = async_to_sync(flow)()
        self.assertEqual(
            msg,
            {
                "type": "error",
                "code": 4004,
                "message": "not_dispatched (got created)",
            },
        )


class WarehouseModelTests(TransactionTestCase):
    def test_validation_and_constraint(self):
        wh = Warehouse(name="Bad", latitude=10, longitude=40)
        with self.assertRaises(ValidationError):
            wh.full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Warehouse.objects.bulk_create(
                    [Warehouse(name="B", latitude=10, longitude=40)]
                )


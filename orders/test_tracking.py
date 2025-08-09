from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase

from Rahim_Online_ClothesStore.asgi import application
from orders.services import create_order_with_items
from orders.ws_codes import WSErr
from orders.models import Order, OrderItem
from product_app.models import Category, Product, Warehouse


class TrackingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="p")
        self.intruder = User.objects.create_user(username="intruder", password="p")
        self.category = Category.objects.create(name="c", slug="c")
        self.product = Product.objects.create(category=self.category, name="p", slug="p", price=10)
        self.wh = Warehouse.objects.create(name="W", latitude=0, longitude=0)

    def _ws(self, user, order_id, item_id):
        comm = WebsocketCommunicator(application, f"/ws/track/{order_id}/{item_id}/")
        comm.scope["user"] = user
        return comm

    def _make(self, user=None, with_wh=True, with_coords=True):
        user = user or self.owner
        order = Order.objects.create(
            user=user,
            full_name="F",
            email="e@e.com",
            address="A",
            latitude=1 if with_coords else None,
            longitude=1 if with_coords else None,
        )
        wh = self.wh if with_wh else None
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            price=10,
            quantity=1,
            warehouse=wh,
            delivery_status="dispatched",
        )
        return order, item

    def test_forbidden_intruder(self):
        order, item = self._make()

        async def flow():
            comm = self._ws(self.intruder, order.id, item.id)
            connected, _ = await comm.connect()
            assert connected
            msg = await comm.receive_json_from()
            code = await comm.wait_closed()
            return msg, code

        msg, code = async_to_sync(flow)()
        self.assertEqual(msg["code"], WSErr.FORBIDDEN)
        self.assertEqual(code, WSErr.FORBIDDEN)

    def test_warehouse_missing(self):
        order, item = self._make(with_wh=False)

        async def flow():
            comm = self._ws(self.owner, order.id, item.id)
            connected, _ = await comm.connect()
            msg = await comm.receive_json_from()
            code = await comm.wait_closed()
            return msg, code

        msg, code = async_to_sync(flow)()
        self.assertEqual(msg["code"], WSErr.WAREHOUSE_MISSING)
        self.assertEqual(code, WSErr.WAREHOUSE_MISSING)

    def test_destination_missing(self):
        order, item = self._make(with_coords=False)

        async def flow():
            comm = self._ws(self.owner, order.id, item.id)
            connected, _ = await comm.connect()
            msg = await comm.receive_json_from()
            code = await comm.wait_closed()
            return msg, code

        msg, code = async_to_sync(flow)()
        self.assertEqual(msg["code"], WSErr.DEST_COORDS_MISSING)
        self.assertEqual(code, WSErr.DEST_COORDS_MISSING)

    def test_item_mismatch(self):
        order1, item1 = self._make()
        order2, item2 = self._make()

        async def flow():
            comm = self._ws(self.owner, order1.id, item2.id)
            connected, _ = await comm.connect()
            msg = await comm.receive_json_from()
            code = await comm.wait_closed()
            return msg, code

        msg, code = async_to_sync(flow)()
        self.assertEqual(msg["code"], WSErr.ITEM_NOT_FOUND)
        self.assertEqual(code, WSErr.ITEM_NOT_FOUND)

    def test_order_not_found(self):
        order, item = self._make()

        async def flow():
            comm = self._ws(self.owner, order.id + 999, item.id)
            connected, _ = await comm.connect()
            msg = await comm.receive_json_from()
            code = await comm.wait_closed()
            return msg, code

        msg, code = async_to_sync(flow)()
        self.assertEqual(msg["code"], WSErr.ORDER_NOT_FOUND)
        self.assertEqual(code, WSErr.ORDER_NOT_FOUND)

    def test_assignment_service_and_signal(self):
        # Service ensures warehouse assignment
        cart = [(self.product, 1)]
        order = create_order_with_items(self.owner, cart, coords=(0, 0))
        self.assertTrue(all(i.warehouse_id for i in order.items.all()))

        # Signal backfills missing warehouse
        order2 = Order.objects.create(
            user=self.owner,
            full_name="F",
            email="e@e.com",
            address="A",
            latitude=0,
            longitude=0,
        )
        item = OrderItem.objects.create(order=order2, product=self.product, price=10, quantity=1)
        self.assertIsNotNone(OrderItem.objects.get(pk=item.pk).warehouse_id)

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DEBUG", "1")
import django
django.setup()

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from Rahim_Online_ClothesStore.asgi import application
from orders.models import Delivery, Order
from django.db import connection

User = get_user_model()


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
)
class DeliveryWebsocketTests(TestCase):
    def test_driver_position_update(self):
        if "users_customuser" not in connection.introspection.table_names():
            self.skipTest("migrations not applied")
        driver = User.objects.create_user(username="drv", password="x")
        cust = User.objects.create_user(username="cust", password="x")
        order = Order.objects.create(user=cust, full_name="A", email="a@a.com")
        delivery = Delivery.objects.create(order=order, driver=driver, status=Delivery.Status.ASSIGNED)

        async def flow():
            comm = WebsocketCommunicator(application, f"/ws/delivery/track/{delivery.id}/")
            connected, _ = await comm.connect()
            assert connected
            comm.scope["user"] = driver
            await comm.send_json_to({"type": "position_update", "lat": 1, "lng": 2})
            msg = await comm.receive_json_from()
            await comm.disconnect()
            return msg

        msg = async_to_sync(flow)()
        self.assertEqual(msg["type"], "position_update")

    def test_consumer_denies_intruder(self):
        if "users_customuser" not in connection.introspection.table_names():
            self.skipTest("migrations not applied")
        driver = User.objects.create_user(username="drv2", password="x")
        intruder = User.objects.create_user(username="bad", password="x")
        order = Order.objects.create(user=driver, full_name="A", email="a@a.com")
        delivery = Delivery.objects.create(order=order, driver=driver)

        async def flow():
            comm = WebsocketCommunicator(application, f"/ws/delivery/track/{delivery.id}/")
            comm.scope["user"] = intruder
            connected, _ = await comm.connect()
            if connected:
                await comm.receive_nothing()
            code = await comm.wait_closed()
            return code

        code = async_to_sync(flow)()
        self.assertEqual(code, 4403)


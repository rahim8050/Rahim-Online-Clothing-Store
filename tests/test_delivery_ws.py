<<<<<<< HEAD
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
            await comm.send_json_to({"type": "position_update", "lat": -1.31, "lng": 36.80})
            msg = await comm.receive_json_from()
            await comm.disconnect()
            return msg

        msg = async_to_sync(flow)()
        self.assertEqual(msg["type"], "position_update")
        self.assertEqual(msg["lat"], -1.31)
        self.assertEqual(msg["lng"], 36.80)
        d = Delivery.objects.get(pk=delivery.id)
        self.assertEqual(float(d.last_lat), -1.31)
        self.assertEqual(float(d.last_lng), 36.80)

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
=======
import json
import pytest
from channels.layers import get_channel_layer
from channels.testing import ApplicationCommunicator

from orders.consumers import DeliveryTrackerConsumer


@pytest.mark.asyncio
async def test_delivery_ws_group_receive_status(monkeypatch, settings):
    settings.CHANNEL_LAYERS = { 'default': { 'BACKEND': 'channels.layers.InMemoryChannelLayer' } }

    # Bypass DB checks in consumer
    async def ok(*args, **kwargs):
        return True
    monkeypatch.setattr(DeliveryTrackerConsumer, "_can_subscribe", ok)

    # Build scope with authenticated user and delivery_id
    class U:
        is_authenticated = True
        id = 99
    scope = {
        "type": "websocket",
        "path": "/ws/delivery/track/123/",
        "user": U(),
        "url_route": {"kwargs": {"delivery_id": "123"}},
    }

    comm = ApplicationCommunicator(DeliveryTrackerConsumer.as_asgi(), scope)
    # Initiate the websocket connection
    await comm.send_input({"type": "websocket.connect"})
    out = await comm.receive_output(timeout=3)
    assert out["type"] == "websocket.accept"

    # Send a group status event and expect it on the socket
    layer = get_channel_layer()
    await layer.group_send("delivery.123", {"type": "delivery.event", "kind": "status", "status": "en_route"})
    out = await comm.receive_output(timeout=3)
    assert out["type"] == "websocket.send"
    data = json.loads(out.get("text") or out.get("bytes").decode())
    assert data == {"type": "status", "status": "en_route"}

    await comm.send_input({"type": "websocket.disconnect"})


@pytest.mark.asyncio
async def test_delivery_ws_group_receive_position(monkeypatch, settings):
    settings.CHANNEL_LAYERS = { 'default': { 'BACKEND': 'channels.layers.InMemoryChannelLayer' } }

    async def ok(*args, **kwargs):
        return True
    monkeypatch.setattr(DeliveryTrackerConsumer, "_can_subscribe", ok)

    class U:
        is_authenticated = True
        id = 42
    scope = {
        "type": "websocket",
        "path": "/ws/delivery/track/7/",
        "user": U(),
        "url_route": {"kwargs": {"delivery_id": "7"}},
    }

    comm = ApplicationCommunicator(DeliveryTrackerConsumer.as_asgi(), scope)
    await comm.send_input({"type": "websocket.connect"})
    out = await comm.receive_output(timeout=3)
    assert out["type"] == "websocket.accept"

    layer = get_channel_layer()
    await layer.group_send("delivery.7", {"type": "delivery.event", "kind": "position_update", "lat": 1.2345, "lng": 2.3456})
    out = await comm.receive_output(timeout=3)
    assert out["type"] == "websocket.send"
    data = json.loads(out.get("text") or out.get("bytes").decode())
    assert data["type"] == "position_update"
    assert float(data["lat"]) == 1.2345
    assert float(data["lng"]) == 2.3456

    await comm.send_input({"type": "websocket.disconnect"})
>>>>>>> development


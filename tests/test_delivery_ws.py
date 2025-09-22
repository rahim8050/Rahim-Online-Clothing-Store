import json

import pytest
from channels.layers import get_channel_layer
from channels.testing import ApplicationCommunicator

from orders.consumers import DeliveryTrackerConsumer


@pytest.mark.asyncio
async def test_delivery_ws_group_receive_status(monkeypatch, settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

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
    await layer.group_send(
        "delivery.123", {"type": "delivery.event", "kind": "status", "status": "en_route"}
    )
    out = await comm.receive_output(timeout=3)
    assert out["type"] == "websocket.send"
    data = json.loads(out.get("text") or out.get("bytes").decode())
    assert data == {"type": "status", "status": "en_route"}

    await comm.send_input({"type": "websocket.disconnect"})


@pytest.mark.asyncio
async def test_delivery_ws_group_receive_position(monkeypatch, settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

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
    await layer.group_send(
        "delivery.7",
        {"type": "delivery.event", "kind": "position_update", "lat": 1.2345, "lng": 2.3456},
    )
    out = await comm.receive_output(timeout=3)
    assert out["type"] == "websocket.send"
    data = json.loads(out.get("text") or out.get("bytes").decode())
    assert data["type"] == "position_update"
    assert float(data["lat"]) == 1.2345
    assert float(data["lng"]) == 2.3456

    await comm.send_input({"type": "websocket.disconnect"})

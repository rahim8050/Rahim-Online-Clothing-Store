import json

import pytest
from channels.auth import AuthMiddlewareStack
from channels.layers import get_channel_layer
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.testing import WebsocketCommunicator

import notifications.routing as notif_routing


@pytest.mark.asyncio
async def test_ws_connect_and_group_send(db, settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    # Build a minimal ASGI app for tests to avoid importing project ASGI
    application = ProtocolTypeRouter(
        {"websocket": AuthMiddlewareStack(URLRouter(notif_routing.websocket_urlpatterns))}
    )
    # Anonymous socket joins 'anon' group in our consumer; we test broadcast path
    communicator = WebsocketCommunicator(application, "/ws/notifications/")
    connected, _ = await communicator.connect()
    assert connected
    layer = get_channel_layer()
    await layer.group_send("anon", {"type": "notify", "payload": {"ping": 1}})
    # First message is hello; then our notify
    _hello = await communicator.receive_from()
    resp = await communicator.receive_from()
    data = json.loads(resp)
    assert data.get("ping") == 1
    await communicator.disconnect()

# orders/routing.py
from django.urls import re_path

from .consumers import DeliveryTrackerConsumer

websocket_urlpatterns = [
    re_path(
        r"^/?ws/delivery/track/(?P<delivery_id>\d+)/?$",
        DeliveryTrackerConsumer.as_asgi(),
    ),
]

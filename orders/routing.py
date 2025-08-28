# orders/routing.py
from django.urls import re_path
from .consumers import DeliveryConsumer, DriverConsumer

websocket_urlpatterns = [
    re_path(r"^ws/delivery/track/(?P<delivery_id>\d+)/$", DeliveryConsumer.as_asgi()),
    re_path(r"^ws/driver/$", DriverConsumer.as_asgi()),  # <-- add this
]

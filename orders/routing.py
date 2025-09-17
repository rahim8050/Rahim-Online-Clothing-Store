# orders/routing.py
from django.urls import re_path

# Prefer DeliveryConsumer; fall back to DeliveryTrackerConsumer for older/newer branches
try:
    from .consumers import DeliveryConsumer  # your per-delivery tracker
except ImportError:  # pragma: no cover
    from .consumers import DeliveryTrackerConsumer as DeliveryConsumer  # alias

# Driver socket is optional; include if present
try:
    from .consumers import DriverConsumer  # optional driver presence channel
    _HAS_DRIVER = True
except ImportError:  # pragma: no cover
    _HAS_DRIVER = False

websocket_urlpatterns = [
    re_path(r"ws/delivery/track/(?P<delivery_id>\d+)/$", DeliveryConsumer.as_asgi()),
]

if _HAS_DRIVER:
    websocket_urlpatterns.append(
        re_path(r"ws/driver/$", DriverConsumer.as_asgi())
    )

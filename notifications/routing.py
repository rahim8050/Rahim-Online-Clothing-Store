# notifications/routing.py
from django.urls import re_path

from .consumers import NotificationsConsumer

# Route for notifications WS. No leading slash per Channels convention.
websocket_urlpatterns = [
    re_path(r"^ws/notifications/?$", NotificationsConsumer.as_asgi()),
]

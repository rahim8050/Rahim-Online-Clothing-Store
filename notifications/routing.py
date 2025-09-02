from django.urls import re_path  # or: from django.urls import path
from .consumers import NotificationConsumer

websocket_urlpatterns = [
    re_path(r"^ws/notifications/$", NotificationConsumer.as_asgi()),
    # OR using path():
    # path("ws/notifications/", NotificationConsumer.as_asgi()),
]

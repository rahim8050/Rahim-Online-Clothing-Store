# notifications/routing.py
from django.urls import re_path
from .consumers import NotificationsConsumer

websocket_urlpatterns = [
    # NOTE: no leading slash here; Channels matches 'ws/notifications/' as-is
    re_path(r"^ws/notifications/$", NotificationsConsumer.as_asgi()),
]

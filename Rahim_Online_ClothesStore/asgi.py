# Rahim_Online_ClothesStore/asgi.py
"""
ASGI config for Rahim_Online_ClothesStore.

Sets up Django (HTTP) and Channels (WebSocket) with safe import order.
"""

import os

# 1) Configure settings BEFORE importing Django/Channels bits
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")

import django
django.setup()  # 2) Initialize Django apps

from django.core.asgi import get_asgi_application
from django.conf import settings
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator

# 3) Import routing AFTER django.setup()
import orders.routing  # must define websocket_urlpatterns
try:
    import notifications.routing
    NOTIF_PATTERNS = getattr(notifications.routing, "websocket_urlpatterns", [])
except Exception:
    NOTIF_PATTERNS = []

# 4) Build the HTTP app
django_asgi_app = get_asgi_application()

# 5) Allowed origins for WS (use http/https scheme here)
DEV_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://localhost:5173",
]
PROD_ORIGINS = [
    "https://your-domain.com",
    "https://www.your-domain.com",
]
ALLOWED_ORIGINS = DEV_ORIGINS if settings.DEBUG else PROD_ORIGINS

# 6) Merge WS routes
websocket_urlpatterns = []
websocket_urlpatterns += getattr(orders.routing, "websocket_urlpatterns", [])
websocket_urlpatterns += NOTIF_PATTERNS

# 7) Final ASGI application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        OriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            ),
            ALLOWED_ORIGINS,
        )
    ),
})

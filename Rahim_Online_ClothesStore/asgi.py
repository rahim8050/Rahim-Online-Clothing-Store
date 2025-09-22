"""
ASGI config for Rahim_Online_ClothesStore.

Sets up Django + Channels routing for HTTP and WebSocket protocols.
"""

import os

# 1) Configure settings BEFORE importing Django components
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")

# 2) Build the Django ASGI app first (ensures app registry is ready)
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

# 3) Now import the rest (safe after Django app init)
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator
from django.conf import settings

# 4) Collect websocket URL patterns from subapps
orders_patterns = []
notif_patterns = []

try:
    from orders import routing as orders_routing

    orders_patterns = getattr(orders_routing, "websocket_urlpatterns", [])
except Exception:
    orders_patterns = []

try:
    from notifications import routing as notifications_routing  # optional app

    notif_patterns = getattr(notifications_routing, "websocket_urlpatterns", [])
except Exception:
    notif_patterns = []

websocket_urlpatterns = [*orders_patterns, *notif_patterns]

# 5) Allowed origins for WS (http/https here; NOT ws://)
DEFAULT_DEV_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://localhost:5173",  # e.g., Vite dev server
]
DEFAULT_PROD_ORIGINS = [
    "https://your-domain.com",
    "https://www.your-domain.com",
]

# Allow override via settings.CHANNELS_ALLOWED_ORIGINS if provided
if hasattr(settings, "CHANNELS_ALLOWED_ORIGINS") and settings.CHANNELS_ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = list(settings.CHANNELS_ALLOWED_ORIGINS)
else:
    ALLOWED_ORIGINS = DEFAULT_DEV_ORIGINS if settings.DEBUG else DEFAULT_PROD_ORIGINS

# 6) Final ASGI application
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            OriginValidator(
                AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
                ALLOWED_ORIGINS,
            )
        ),
    }
)

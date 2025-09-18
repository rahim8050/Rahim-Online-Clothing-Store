"""ASGI config for Rahim_Online_ClothesStore.

Sets up Django + Channels routing for HTTP and WebSocket protocols.
"""

import os

# 1) Configure settings BEFORE importing Django components
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")

# 2) Build the Django ASGI app first (so app registry is ready for later imports)
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

# 3) Now import the rest (safe to import settings and Channels bits)
from django.conf import settings
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator

# 4) Collect websocket URL patterns from subapps (optional/robust)
orders_patterns = []
notif_patterns = []

try:
    from orders import routing as orders_routing
    orders_patterns = getattr(orders_routing, "websocket_urlpatterns", [])
except Exception:
    orders_patterns = []

try:
    # If you have a notifications app; otherwise this stays empty
    from notifications import routing as notifications_routing
    notif_patterns = getattr(notifications_routing, "websocket_urlpatterns", [])
except Exception:
    notif_patterns = []

websocket_urlpatterns = [*orders_patterns, *notif_patterns]

# 5) Allowed origins for WS (http/https schemes here; NOT ws://)
DEV_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://localhost:5173",  # Vite dev server
]
PROD_ORIGINS = [
    "https://your-domain.com",
    "https://www.your-domain.com",
]
ALLOWED_ORIGINS = DEV_ORIGINS if settings.DEBUG else PROD_ORIGINS

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

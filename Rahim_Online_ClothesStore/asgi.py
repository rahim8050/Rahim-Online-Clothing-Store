# Rahim_Online_ClothesStore/asgi.py
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")

import django
django.setup()

from django.core.asgi import get_asgi_application
from django.conf import settings
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator

# Import routing AFTER setup
import orders.routing
try:
    import notifications.routing
    NOTIF_PATTERNS = getattr(notifications.routing, "websocket_urlpatterns", [])
except Exception:
    NOTIF_PATTERNS = []

django_asgi_app = get_asgi_application()

# Allowed page origins (http/https, not ws)
DEV_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://localhost:5173",  # Vite, if you use it
]
PROD_ORIGINS = [
    "https://your-domain.com",
    "https://www.your-domain.com",
]
ALLOWED_ORIGINS = DEV_ORIGINS if settings.DEBUG else PROD_ORIGINS

# Merge WS routes
websocket_urlpatterns = []
websocket_urlpatterns += getattr(orders.routing, "websocket_urlpatterns", [])
websocket_urlpatterns += NOTIF_PATTERNS

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        OriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            ),
            ALLOWED_ORIGINS,
        )

import django
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")
django.setup()  # settings loaded before app imports

django_asgi_app = get_asgi_application()

# Import AFTER setup
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import orders.routing
import notifications.routing

# Combine all websocket routes
websocket_urlpatterns = []
websocket_urlpatterns += getattr(orders.routing, "websocket_urlpatterns", [])
websocket_urlpatterns += getattr(notifications.routing, "websocket_urlpatterns", [])

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)   # <-- use the combined list

    ),
})

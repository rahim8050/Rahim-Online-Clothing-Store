# Rahim_Online_ClothesStore/asgi.py
import os
import django
from django.core.asgi import get_asgi_application

from django.conf import settings
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator
import orders.routing  # make sure orders/routing.py defines websocket_urlpatterns


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")
django.setup()  # <-- ensure settings are loaded before any app imports

django_asgi_app = get_asgi_application()


# Origins allowed to load your page and open the WS (Origin header)
# Use http/https here (NOT ws://); this checks the page's origin, not the socket scheme.
DEV_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://localhost:5173",   # Vite dev server (if you serve the page from here)
]
PROD_ORIGINS = [
    "https://your-domain.com",
    "https://www.your-domain.com",
]

ALLOWED_ORIGINS = (DEV_ORIGINS if settings.DEBUG else PROD_ORIGINS)

application = ProtocolTypeRouter({
    "http": django_asgi_app,

    # Validate both Host header (against settings.ALLOWED_HOSTS) and page Origin
    "websocket": AllowedHostsOriginValidator(
        OriginValidator(
            AuthMiddlewareStack(
                URLRouter(orders.routing.websocket_urlpatterns)
            ),
            ALLOWED_ORIGINS
        )
    ),
})

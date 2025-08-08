"""
ASGI config for Rahim_Online_ClothesStore project.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()
import orders.routing

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(orders.routing.websocket_urlpatterns))
        ),
    }
)

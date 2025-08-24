import os, django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator
from django.core.asgi import get_asgi_application
from orders import routing as orders_routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # Harden WebSocket origins and hosts
    "websocket": AllowedHostsOriginValidator(
        OriginValidator(
            AuthMiddlewareStack(
                URLRouter(orders_routing.websocket_urlpatterns)
            ),
            [
                "http://localhost:5173",
                "http://127.0.0.1:8000",
                "https://your-domain.com",
                "https://www.your-domain.com",
            ],
        )
    ),
})


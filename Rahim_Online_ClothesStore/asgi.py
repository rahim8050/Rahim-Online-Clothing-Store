# Rahim_Online_ClothesStore/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator, OriginValidator

from orders import routing as orders_routing  # contains websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")

django_asgi_app = get_asgi_application()

# Ensure settings module is set before anything Django-related
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")

# Initialize Django first (apps ready)
import django
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

# Import AFTER django.setup()
import orders.routing


django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,

    "websocket": AllowedHostsOriginValidator(          # host must be in ALLOWED_HOSTS
        OriginValidator(                               # origin must be in this allowlist
            AuthMiddlewareStack(
                URLRouter(orders_routing.websocket_urlpatterns)
            ),
            [
                "http://127.0.0.1:8000",
                "http://localhost:8000",
                "http://localhost:5173",              # Vite dev server, if you open pages from here
                "https://your-domain.com",
                "https://www.your-domain.com",
            ],

    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(orders.routing.websocket_urlpatterns)

        )
    ),
})

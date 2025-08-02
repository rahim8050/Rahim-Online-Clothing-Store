"""ASGI config for Rahim_Online_ClothesStore project."""
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import orders.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Rahim_Online_ClothesStore.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(orders.routing.websocket_urlpatterns)
    ),
})

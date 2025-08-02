"""
ASGI config for Rahim_Online_ClothesStore project.
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Rahim_Online_ClothesStore.settings')
import django
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import orders.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            orders.routing.websocket_urlpatterns
        )
    ),
})

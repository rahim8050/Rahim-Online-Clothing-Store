"""
ASGI config for Rahim_Online_ClothesStore project.
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Rahim_Online_ClothesStore.settings')
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import orders.routing as orders_routing

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": URLRouter(orders_routing.websocket_urlpatterns),
    }
)

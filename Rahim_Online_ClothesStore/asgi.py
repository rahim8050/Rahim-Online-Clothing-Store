# Rahim_Online_ClothesStore/asgi.py
import os
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

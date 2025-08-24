from django.urls import path
from .consumers import DeliveryConsumer

websocket_urlpatterns = [
    # Single endpoint for delivery tracking
    path("ws/delivery/track/<int:delivery_id>/", DeliveryConsumer.as_asgi()),
]

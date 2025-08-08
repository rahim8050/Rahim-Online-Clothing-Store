from django.urls import path
from .consumers import DeliveryTrackerConsumer

websocket_urlpatterns = [
    path("ws/track/<int:order_id>/<int:item_id>/", DeliveryTrackerConsumer.as_asgi()),
]

from django.urls import re_path
from .consumers import DeliveryConsumer

websocket_urlpatterns = [
    re_path(r"^ws/deliveries/(?P<delivery_id>\d+)/$", DeliveryConsumer.as_asgi())
]

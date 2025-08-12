from django.apps import apps
from rest_framework import serializers

from product_app.models import Product
from orders.models import OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "order", "product", "price", "quantity", "delivery_status"]


class ProductSerializer(serializers.ModelSerializer):
    # If your FK on OrderItem uses related_name="order_items", this is fine.
    # If not, change `source` to the actual related name (e.g. "orderitem_set").
    order_items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "price", "available", "order_items"]


# ---- Optional Delivery serializer (won't explode if model is absent) ----
class EmptySerializer(serializers.Serializer):
    """Used when Delivery model doesn't exist."""
    pass

try:
    DeliveryModel = apps.get_model("orders", "Delivery")  # raises LookupError if absent
except LookupError:
    DeliveryModel = None

if DeliveryModel is not None:
    class DeliverySerializer(serializers.ModelSerializer):
        class Meta:
            model = DeliveryModel
            fields = "__all__"
else:
    # Keep a symbol so `from .serializers import DeliverySerializer` never fails.
    DeliverySerializer = EmptySerializer


class DeliveryAssignSerializer(serializers.Serializer):
    driver_id = serializers.IntegerField()


class DeliveryUnassignSerializer(serializers.Serializer):
    pass


class DeliveryStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[c[0] for c in DeliveryModel.Status.choices] if DeliveryModel else [])

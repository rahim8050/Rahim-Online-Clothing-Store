from rest_framework import serializers

from .models import Order, OrderItem
from product_app.serializers_v1 import ProductV1Serializer


class OrderItemV1Serializer(serializers.ModelSerializer):
    product = ProductV1Serializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_version",
            "price",
            "quantity",
            "delivery_status",
            "warehouse",
        ]


class OrderV1Serializer(serializers.ModelSerializer):
    items = OrderItemV1Serializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "full_name",
            "email",
            "address",
            "latitude",
            "longitude",
            "location_address",
            "coords_locked",
            "coords_source",
            "coords_updated_at",
            "dest_address_text",
            "dest_lat",
            "dest_lng",
            "dest_source",
            "user",
            "created_at",
            "updated_at",
            "paid",
            "payment_status",
            "payment_intent_id",
            "stripe_receipt_url",
            "items",
        ]
        read_only_fields = [
            "id",
            "user",
            "created_at",
            "updated_at",
            "paid",
            "payment_status",
            "payment_intent_id",
            "stripe_receipt_url",
            "items",
        ]


class CheckoutV1Serializer(serializers.Serializer):
    cart_id = serializers.IntegerField()
    full_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    address = serializers.CharField(max_length=250)
    dest_address_text = serializers.CharField(max_length=255)
    dest_lat = serializers.DecimalField(max_digits=9, decimal_places=6)
    dest_lng = serializers.DecimalField(max_digits=9, decimal_places=6)
    payment_method = serializers.CharField(max_length=20)


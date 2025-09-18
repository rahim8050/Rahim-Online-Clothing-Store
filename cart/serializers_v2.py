from decimal import Decimal
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Cart, CartItem
from product_app.serializers_v1 import ProductV1Serializer
from product_app.models import Product


class CartItemReadSerializer(serializers.ModelSerializer):
    product = ProductV1Serializer(read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "product", "quantity", "line_total", "created_at"]

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))  # guessed
    def get_line_total(self, obj) -> str:
        return str(Decimal(obj.product.price) * obj.quantity)


class CartItemWriteSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1, default=1)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemReadSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "status",
            "items",
            "total_price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "items", "total_price"]

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))  # guessed
    def get_total_price(self, obj) -> str:
        total = Decimal("0.00")
        for item in getattr(obj, "_prefetched_items", obj.items.select_related("product").all()):
            total += Decimal(item.product.price) * item.quantity
        return str(total)


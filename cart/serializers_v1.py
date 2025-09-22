from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from product_app.models import Product
from product_app.serializers_v1 import ProductV1Serializer

from .models import Cart, CartItem


class CartItemV1ReadSerializer(serializers.ModelSerializer):
    product = ProductV1Serializer(read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "quantity", "is_selected"]


class CartItemV1WriteSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1, default=1)


class CartV1Serializer(serializers.ModelSerializer):
    items = CartItemV1ReadSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "created_at", "updated_at", "items", "total_price"]

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))  # guessed
    def get_total_price(self, obj) -> str:
        return str(obj.get_total_price())

from django.contrib.auth import get_user_model
from rest_framework import serializers

from orders.models import Order, OrderItem
from product_app.models import Category, Product, ProductStock, Warehouse

User = get_user_model()


# ------------------ Catalog ------------------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductSerializer(serializers.ModelSerializer):
    owner: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(
        read_only=True
    )
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price",
            "available",
            "created",
            "updated",
            "product_version",
            "image",
            "category",
            "owner",
        ]
        read_only_fields = ["id", "created", "updated", "product_version", "owner"]


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "name", "latitude", "longitude", "address", "is_active"]


class ProductStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductStock
        fields = ["id", "product", "warehouse", "quantity"]


# ------------------ Orders -------------------
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order",
            "product",
            "product_version",
            "price",
            "quantity",
            "warehouse",
            "delivery_status",
        ]


class OrderSerializer(serializers.ModelSerializer):
    user: serializers.PrimaryKeyRelatedField = serializers.PrimaryKeyRelatedField(
        read_only=True
    )

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
        ]

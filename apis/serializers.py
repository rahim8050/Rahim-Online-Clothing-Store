from django.apps import apps
from rest_framework import serializers
from product_app.models import Product
from orders.models import OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "order", "product", "price", "quantity", "delivery_status"]

class ProductSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "price", "available", "order_items"]

# Delivery serializer is optional
Delivery = apps.get_model('orders', 'Delivery')
if Delivery:
    class DeliverySerializer(serializers.ModelSerializer):
        class Meta:
            model = Delivery
            fields = "__all__"
else:
    DeliverySerializer = None

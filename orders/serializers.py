from rest_framework import serializers

from .models import Delivery


class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = [
            "id",
            "order",
            "status",
            "driver",
            "assigned_at",
            "picked_up_at",
            "delivered_at",
            "origin_lat",
            "origin_lng",
            "dest_lat",
            "dest_lng",
            "last_lat",
            "last_lng",
            "last_ping_at",
        ]
        read_only_fields = [
            "driver",
            "assigned_at",
            "picked_up_at",
            "delivered_at",
            "last_lat",
            "last_lng",
            "last_ping_at",
            "status",
        ]


class DriverDeliveryListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = [
            "id",
            "order",
            "status",
            "dest_lat",
            "dest_lng",
            "last_lat",
            "last_lng",
            "last_ping_at",
        ]

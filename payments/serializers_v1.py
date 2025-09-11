from decimal import Decimal
from rest_framework import serializers


class CheckoutInitV1Serializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(max_length=3)
    gateway = serializers.CharField(max_length=20)
    method = serializers.CharField(max_length=20)
    idempotency_key = serializers.CharField(max_length=64)


class CheckoutInitV1ResponseSerializer(serializers.Serializer):  # guessed; refine as needed
    ok = serializers.BooleanField()
    reference = serializers.CharField()
    gateway = serializers.CharField(max_length=20)

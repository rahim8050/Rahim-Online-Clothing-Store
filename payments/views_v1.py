from decimal import Decimal
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .serializers_v1 import CheckoutInitV1Serializer, CheckoutInitV1ResponseSerializer
from .services import init_checkout
from .models import Transaction
from orders.models import Order


class CheckoutInitV1(APIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CheckoutInitV1Serializer

    @extend_schema(request=CheckoutInitV1Serializer, responses=CheckoutInitV1ResponseSerializer)
    def post(self, request):
        ser = CheckoutInitV1Serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        order = get_object_or_404(Order, pk=data["order_id"], user=request.user)
        amount = Decimal(str(data["amount"]))
        if amount != order.get_total_cost():
            return Response({"ok": False, "error": "amount_mismatch"}, status=400)

        txn = init_checkout(
            order=order,
            user=request.user,
            method=data["method"],
            gateway=data["gateway"],
            amount=amount,
            currency=data["currency"],
            idempotency_key=data["idempotency_key"],
            reference=f"ORD-{order.id}-{request.user.id}",
        )
        return Response({
            "ok": True,
            "reference": txn.reference,
            "gateway": txn.gateway,
        })


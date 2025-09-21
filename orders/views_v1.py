from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import decorators, permissions, status, viewsets
from rest_framework.response import Response

from cart.models import Cart, CartItem

from .models import Order, OrderItem
from .serializers_v1 import CheckoutV1Serializer, OrderV1Serializer


class OrderV1ViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderV1Serializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        qs = Order.objects.all().order_by("-created_at")
        if u.is_staff or u.is_superuser:
            return qs
        return qs.filter(user=u)

    @decorators.action(detail=False, methods=["post"], url_path="checkout")
    @transaction.atomic
    def checkout(self, request):
        """Create an Order from a Cart.

        Expects JSON body with cart_id, address + destination info, and payment_method.
        """
        ser = CheckoutV1Serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        u = request.user
        if not u.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)

        cart = get_object_or_404(
            Cart.objects.prefetch_related("items__product"), pk=data["cart_id"]
        )
        if not cart.items.exists():
            return Response({"detail": "Cart is empty."}, status=400)

        order = Order.objects.create(
            full_name=data["full_name"],
            email=data["email"],
            address=data["address"],
            dest_address_text=data["dest_address_text"],
            dest_lat=data["dest_lat"],
            dest_lng=data["dest_lng"],
            user=u,
            payment_method=data["payment_method"],
        )

        items = []
        for item in cart.items.select_related("product"):
            p = item.product
            items.append(
                OrderItem(
                    order=order,
                    product=p,
                    product_version=getattr(p, "product_version", 1),
                    price=p.price,
                    quantity=item.quantity,
                )
            )
        OrderItem.objects.bulk_create(items)

        # Deactivate cart by clearing items
        CartItem.objects.filter(cart=cart).delete()

        return Response(OrderV1Serializer(order).data, status=status.HTTP_201_CREATED)

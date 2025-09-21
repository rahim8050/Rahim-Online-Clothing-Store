from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import decorators, permissions, viewsets
from rest_framework.response import Response

from .models import Cart, CartItem
from .serializers_v1 import CartItemV1WriteSerializer, CartV1Serializer


class CartV1ViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Cart.objects.prefetch_related("items__product").all().order_by("-updated_at")
    serializer_class = CartV1Serializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Authenticated users: show recent carts (debug/dev convenience)
        return super().get_queryset()

    @decorators.action(detail=False, methods=["post"], url_path="my_active")
    def my_active(self, request):
        """Get or create an active cart for the user.

        Since Cart has no user FK, we bind a cart id to the user in cache.
        """
        u = request.user
        if not (u and u.is_authenticated):
            return Response({"detail": "Authentication required."}, status=401)
        key = f"user_cart_{u.id}"
        cart_id = cache.get(key)
        cart = None
        if cart_id:
            cart = Cart.objects.filter(pk=cart_id).first()
        if cart is None:
            cart = Cart.objects.create()
            cache.set(key, cart.id, timeout=60 * 60 * 6)  # 6 hours
        return Response(CartV1Serializer(cart).data)

    @decorators.action(detail=True, methods=["post"], url_path="add_item")
    def add_item(self, request, pk=None):
        cart = get_object_or_404(Cart, pk=pk)
        ser = CartItemV1WriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        product = ser.validated_data["product"]
        qty = ser.validated_data["quantity"]
        item, _ = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={"quantity": qty}
        )
        if not _:
            item.quantity += qty
            item.save(update_fields=["quantity"])
        return Response(CartV1Serializer(cart).data)

    @decorators.action(detail=True, methods=["post"], url_path="remove_item")
    def remove_item(self, request, pk=None):
        cart = get_object_or_404(Cart, pk=pk)
        item_id = request.data.get("item_id")
        if not item_id:
            return Response({"item_id": "This field is required."}, status=400)
        CartItem.objects.filter(pk=item_id, cart=cart).delete()
        return Response(CartV1Serializer(cart).data)

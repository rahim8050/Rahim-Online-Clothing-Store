from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import decorators, mixins, permissions, viewsets
from rest_framework.response import Response

from .models import Cart, CartItem
from .serializers_v2 import CartItemWriteSerializer, CartSerializer


class CartViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Cart v2 API with strong ownership and safe concurrency.

    All endpoints require authentication and only expose the caller's carts.

    Actions:
    - GET /carts/my/active/ → get/create active cart for the user
    - POST /carts/{id}/add_item/ {product, quantity}
    - POST /carts/{id}/update_item/ {item_id, quantity}
    - POST /carts/{id}/remove_item/ {item_id}
    - POST /carts/{id}/clear/
    """

    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Cart.objects.filter(user=self.request.user)
            .prefetch_related("items__product")
            .order_by("-updated_at")
        )

    @decorators.action(detail=False, methods=["get"], url_path="my/active")
    @transaction.atomic
    def my_active(self, request):
        """Return the single active cart for the user, creating it if missing.

        Enforces uniqueness using a SELECT ... FOR UPDATE window to avoid races.
        """
        u = request.user
        qs = Cart.objects.select_for_update().filter(user=u, status=Cart.Status.ACTIVE)
        cart = qs.first()
        if cart is None:
            cart = Cart.objects.create(user=u, status=Cart.Status.ACTIVE)
        return Response(CartSerializer(cart).data)

    def _ensure_active_owned(self, request, pk) -> Cart:
        cart = get_object_or_404(self.get_queryset(), pk=pk)
        if cart.status != Cart.Status.ACTIVE:
            # Raise via DRF shortcut
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"status": "Cart is not active."})
        return cart

    @decorators.action(detail=True, methods=["post"], url_path="add_item")
    @transaction.atomic
    def add_item(self, request, pk=None):
        cart = self._ensure_active_owned(request, pk)
        ser = CartItemWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        product = ser.validated_data["product"]
        qty = ser.validated_data["quantity"]

        # Lock the cart row to guard against concurrent writes
        Cart.objects.select_for_update().filter(pk=cart.pk).first()

        item, created = CartItem.objects.select_for_update().get_or_create(
            cart=cart, product=product, defaults={"quantity": qty}
        )
        if not created:
            CartItem.objects.filter(pk=item.pk).update(quantity=F("quantity") + qty)
            item.refresh_from_db()
        return Response(CartSerializer(cart).data)

    @decorators.action(detail=True, methods=["post"], url_path="update_item")
    @transaction.atomic
    def update_item(self, request, pk=None):
        cart = self._ensure_active_owned(request, pk)
        item_id = request.data.get("item_id")
        qty = request.data.get("quantity")
        if not item_id:
            return Response({"item_id": "This field is required."}, status=400)
        try:
            qty = int(qty)
        except Exception:
            return Response({"quantity": "Must be an integer >= 1."}, status=400)
        if qty < 1:
            return Response({"quantity": "Must be >= 1."}, status=400)

        # Lock item row and set exact quantity
        item = get_object_or_404(CartItem.objects.select_for_update(), pk=item_id, cart=cart)
        item.quantity = qty
        item.save(
            update_fields=(
                ["quantity", "updated_at"] if hasattr(item, "updated_at") else ["quantity"]
            )
        )
        return Response(CartSerializer(cart).data)

    @decorators.action(detail=True, methods=["post"], url_path="remove_item")
    @transaction.atomic
    def remove_item(self, request, pk=None):
        cart = self._ensure_active_owned(request, pk)
        item_id = request.data.get("item_id")
        if not item_id:
            return Response({"item_id": "This field is required."}, status=400)
        deleted, _ = CartItem.objects.filter(pk=item_id, cart=cart).delete()
        return Response({"removed": bool(deleted)})

    @decorators.action(detail=True, methods=["post"], url_path="clear")
    @transaction.atomic
    def clear(self, request, pk=None):
        cart = self._ensure_active_owned(request, pk)
        CartItem.objects.filter(cart=cart).delete()
        return Response({"cleared": True})

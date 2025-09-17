from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from product_app.models import Product
from .models import Cart, CartItem
from .guest import (
    get_signed_cookie,
    get_or_create_guest_cart,
    set_signed_cookie,
    clear_cookie,
)
from .serializers_v2 import CartSerializer, CartItemWriteSerializer


class GuestCartViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Guest cart endpoints using a signed cookie.

    - POST /guest/carts/my_active/
    - POST /guest/carts/{id}/add_item/
    - POST /guest/carts/{id}/update_item/
    - POST /guest/carts/{id}/remove_item/
    - POST /guest/carts/{id}/clear/
    """

    permission_classes = [AllowAny]
    serializer_class = CartSerializer

    def _cookie_cart(self, request) -> Cart | None:
        cid = get_signed_cookie(request)
        if not cid:
            return None
        try:
            return (
                Cart.objects.prefetch_related("items__product")
                .get(pk=cid, user__isnull=True, status=Cart.Status.ACTIVE)
            )
        except Cart.DoesNotExist:
            return None

    def get_queryset(self):
        c = self._cookie_cart(self.request)
        return Cart.objects.filter(pk=c.pk) if c else Cart.objects.none()

    @action(detail=False, methods=["post"], url_path="my_active")
    def my_active(self, request):
        cart = self._cookie_cart(request)
        created = False
        if not cart:
            cart = get_or_create_guest_cart()
            created = True
        data = self.get_serializer(cart).data
        resp = Response(
            data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
        if created:
            set_signed_cookie(resp, cart.pk)
        return resp

    @action(detail=True, methods=["post"], url_path="add_item")
    def add_item(self, request, pk=None):
        cart = self._cookie_cart(request)
        if not cart or str(cart.pk) != str(pk):
            return Response({"detail": "Guest cart not found"}, status=404)
        ser = CartItemWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        product = ser.validated_data["product"]
        qty = ser.validated_data["quantity"]
        with transaction.atomic():
            Cart.objects.select_for_update().filter(pk=cart.pk).first()
            Product.objects.select_for_update().get(pk=product.pk)
            item, created = CartItem.objects.select_for_update().get_or_create(
                cart=cart, product=product, defaults={"quantity": qty}
            )
            if not created:
                CartItem.objects.filter(pk=item.pk).update(quantity=F("quantity") + qty)
        cart.refresh_from_db()
        return Response(self.get_serializer(cart).data)

    @action(detail=True, methods=["post"], url_path="update_item")
    def update_item(self, request, pk=None):
        cart = self._cookie_cart(request)
        if not cart or str(cart.pk) != str(pk):
            return Response({"detail": "Guest cart not found"}, status=404)
        try:
            item_id = int(request.data.get("item_id"))
            quantity = int(request.data.get("quantity", 1))
        except Exception:
            return Response({"detail": "Invalid item_id/quantity"}, status=400)
        if quantity < 1:
            return Response({"detail": "quantity must be >= 1"}, status=400)
        with transaction.atomic():
            CartItem.objects.select_for_update().filter(pk=item_id, cart=cart).update(
                quantity=quantity
            )
        cart.refresh_from_db()
        return Response(self.get_serializer(cart).data)

    @action(detail=True, methods=["post"], url_path="remove_item")
    def remove_item(self, request, pk=None):
        cart = self._cookie_cart(request)
        if not cart or str(cart.pk) != str(pk):
            return Response({"detail": "Guest cart not found"}, status=404)
        item_id = request.data.get("item_id")
        deleted, _ = CartItem.objects.filter(pk=item_id, cart=cart).delete()
        return Response({"removed": bool(deleted)})

    @action(detail=True, methods=["post"], url_path="clear")
    def clear(self, request, pk=None):
        cart = self._cookie_cart(request)
        if not cart or str(cart.pk) != str(pk):
            return Response({"detail": "Guest cart not found"}, status=404)
        CartItem.objects.filter(cart=cart).delete()
        return Response({"cleared": True})


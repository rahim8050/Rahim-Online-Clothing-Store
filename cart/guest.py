from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import F

from .models import Cart, CartItem


# Cookie configuration
COOKIE_NAME = "guest_cart_id"
COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days


def get_signed_cookie(request) -> int | None:
    """Return cart id from signed cookie or None if absent/invalid."""
    val = request.COOKIES.get(COOKIE_NAME)
    if not val:
        return None
    try:
        raw = signing.Signer().unsign(val)
        return int(raw)
    except Exception:
        return None


def set_signed_cookie(response, cart_id: int):
    """Attach signed cookie for the guest cart to the response."""
    val = signing.Signer().sign(str(cart_id))
    response.set_cookie(
        COOKIE_NAME,
        val,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )


def clear_cookie(response):
    response.delete_cookie(COOKIE_NAME)


def get_or_create_guest_cart() -> Cart:
    """Create a fresh guest cart; guest carts have user=None."""
    return Cart.objects.create(user=None, status=Cart.Status.ACTIVE)


def merge_guest_into_user(guest_cart: Cart, user_cart: Cart) -> Cart:
    """Merge all items from guest_cart into user_cart, summing quantities.

    Idempotent and safe under concurrent logins via select_for_update locks.
    Deletes the guest_cart after successful merge.
    """
    with transaction.atomic():
        # lock both carts
        user_cart = Cart.objects.select_for_update().get(pk=user_cart.pk)
        guest_cart = Cart.objects.select_for_update().get(pk=guest_cart.pk)

        for item in (
            CartItem.objects.select_for_update()
            .filter(cart=guest_cart)
            .select_related("product")
        ):
            target, created = CartItem.objects.select_for_update().get_or_create(
                cart=user_cart,
                product=item.product,
                defaults={"quantity": item.quantity},
            )
            if not created:
                CartItem.objects.filter(pk=target.pk).update(
                    quantity=F("quantity") + item.quantity
                )

        # cleanup guest cart
        CartItem.objects.filter(cart=guest_cart).delete()
        guest_cart.delete()
    return user_cart


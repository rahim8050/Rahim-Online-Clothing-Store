from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import Cart
from .guest import get_signed_cookie, merge_guest_into_user


@receiver(user_logged_in)
def merge_guest_cart_on_login(sender, user, request, **kwargs):
    """On successful login, merge a guest cart (if any) into the user's active cart.

    This is idempotent and safe under contention: the merge routine locks rows.
    """
    try:
        cid = get_signed_cookie(request)
        if not cid:
            return
        guest = Cart.objects.filter(
            pk=cid, user__isnull=True, status=Cart.Status.ACTIVE
        ).first()
        if not guest:
            return
        user_cart, _ = Cart.objects.get_or_create(user=user, status=Cart.Status.ACTIVE)
        merge_guest_into_user(guest, user_cart)
    except Exception:
        # Be conservative: never block login path due to cart merge errors.
        return


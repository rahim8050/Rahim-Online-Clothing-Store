from .models import Cart


def cart_counter(request):
    cart_id = request.session.get("cart_id")
    count = 0

    if cart_id:
        try:
            cart = Cart.objects.get(id=cart_id)
            count = sum(item.quantity for item in cart.items.all())
        except Cart.DoesNotExist:
            count = 0

    return {"cart_total_items": count}

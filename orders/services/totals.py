from orders.money import D, q2


def safe_order_total(order):
    items = order.items.select_related("product").all()

    subtotal = sum((D(i.price) * i.quantity for i in items), D("0.00"))

    # Since shipping_fee, discount, tax are NOT fields on Order, treat them as zero
    shipping = D("0.00")
    discount = D("0.00")
    tax = D("0.00")

    return q2(subtotal - discount + shipping + tax)


# orders/services/totals.py
from decimal import ROUND_HALF_UP, Decimal

Q2 = Decimal("0.01")


def safe_order_total(order) -> Decimal:
    # Use OrderItem.price (copied at checkout), not Product.price
    total = sum((it.price * it.quantity for it in order.items.all()), Decimal("0.00"))
    return total.quantize(Q2, rounding=ROUND_HALF_UP)

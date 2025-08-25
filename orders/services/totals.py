"""Helpers for computing order totals using Decimals only."""

# Re-use Decimal utilities from the money module so that any value – even a
# float – is safely converted before arithmetic.  This prevents mixing native
# Python ``float`` values with :class:`decimal.Decimal` which would otherwise
# raise ``TypeError`` during operations such as subtraction.
from orders.money import D, q2

def safe_order_total(order):
    items = order.items.select_related("product").all()

    # Ensure each item's price participates in Decimal arithmetic.  Starting the
    # sum with ``D('0.00')`` guarantees the result is also a ``Decimal``.
    subtotal = sum((D(i.price) * i.quantity for i in items), D("0.00"))

    # Values stored on the order (e.g. shipping_fee) may be floats.  Wrapping
    # them with ``D`` normalises them to Decimals before performing the maths
    # below, avoiding ``float - Decimal`` type errors.
    shipping = D(getattr(order, "shipping_fee", 0) or 0)
    discount = D(getattr(order, "discount", 0) or 0)
    tax = D(getattr(order, "tax", 0) or 0)

    return q2(subtotal - discount + shipping + tax)

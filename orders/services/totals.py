from decimal import Decimal
from orders.money import q2

def safe_order_total(order):
    items = order.items.select_related("product").all()
    subtotal = sum((i.price * i.quantity for i in items), Decimal("0.00"))
    shipping = getattr(order, "shipping_fee", None) or Decimal("0.00")
    discount = getattr(order, "discount", None) or Decimal("0.00")
    tax      = getattr(order, "tax", None) or Decimal("0.00")
    return q2(subtotal - discount + shipping + tax)

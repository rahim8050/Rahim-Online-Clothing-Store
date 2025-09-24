from decimal import ROUND_HALF_UP, Decimal

Q2 = Decimal("0.01")


def safe_order_total(order) -> Decimal:
    """Sum order item totals using stored prices and quantize to two decimals."""
    total = sum((it.price * it.quantity for it in order.items.all()), Decimal("0.00"))
    return total.quantize(Q2, rounding=ROUND_HALF_UP)

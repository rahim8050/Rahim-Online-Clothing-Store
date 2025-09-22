# orders/money.py
from decimal import ROUND_HALF_UP, Decimal

TWODP = Decimal("0.01")


def D(x) -> Decimal:
    """
    Safe Decimal constructor: accepts Decimal/int/str/float.
    Does NOT quantize (so you can sum precisely); quantize at the end.
    """
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def q2(x: Decimal) -> Decimal:
    """Quantize to 2 dp with bankers-friendly rounding."""
    return D(x).quantize(TWODP, rounding=ROUND_HALF_UP)


def to_minor_units(amount: Decimal, multiplier: Decimal = Decimal("100")) -> int:
    """
    Convert whole-currency Decimal (e.g., KES 123.45) to minor units (e.g., 12345).
    """
    return int((D(amount) * multiplier).to_integral_value(rounding=ROUND_HALF_UP))

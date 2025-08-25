# orders/money.py
from decimal import Decimal, ROUND_HALF_UP

_Q2 = Decimal("0.01")

def D(x):
    return x if isinstance(x, Decimal) else Decimal(str(x))

def q2(x):
    return D(x).quantize(_Q2, rounding=ROUND_HALF_UP)

def to_minor_units(amount) -> int:
    # 2dp HALF_UP -> integer minor units
    return int((q2(amount) * 100).to_integral_value(rounding=ROUND_HALF_UP))

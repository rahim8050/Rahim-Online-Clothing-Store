# orders/assignment.py
import math
from decimal import Decimal
from typing import Union

Number = Union[float, int, Decimal]


def _to_float(x: Number | None) -> float | None:
    """Normalize Decimal/int to float for trig math."""
    return float(x) if x is not None else None


def _haversine(
    lat1: Number | None,
    lng1: Number | None,
    lat2: Number | None,
    lng2: Number | None,
) -> float:
    # Coerce everything to float once, at the edge
    lat1_f = _to_float(lat1)
    lng1_f = _to_float(lng1)
    lat2_f = _to_float(lat2)
    lng2_f = _to_float(lng2)

    # If any coord missing, make distance infinite so it won't be chosen
    if None in (lat1_f, lng1_f, lat2_f, lng2_f):
        return float("inf")

    assert lat1_f is not None
    assert lng1_f is not None
    assert lat2_f is not None
    assert lng2_f is not None

    R = 6_371_000.0  # meters
    phi1, phi2 = math.radians(lat1_f), math.radians(lat2_f)
    dphi = math.radians(lat2_f - lat1_f)
    dlambda = math.radians(lng2_f - lng1_f)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def pick_warehouse(lat: Number | None, lng: Number | None):
    """Return the nearest active Warehouse with coordinates."""
    from .models import Warehouse  # local import avoids early app loading issues

    lat_f = _to_float(lat)
    lng_f = _to_float(lng)
    if lat_f is None or lng_f is None:
        return None

    qs = Warehouse.objects.filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
    )

    chosen = None
    best = float("inf")
    for wh in qs.iterator():
        dist = _haversine(lat_f, lng_f, wh.latitude, wh.longitude)
        if dist < best:
            best = dist
            chosen = wh
    return chosen

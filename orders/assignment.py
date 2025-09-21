# orders/assignment.py
import math
from decimal import Decimal
from typing import Union

Number = Union[float, int, Decimal]


def _to_float(x: Number | None) -> float | None:
    """Normalize Decimal/int to float for trig math."""
    return float(x) if x is not None else None


def _haversine(lat1: Number, lng1: Number, lat2: Number, lng2: Number) -> float:
    # Coerce everything to float once, at the edge
    lat1 = _to_float(lat1)
    lng1 = _to_float(lng1)
    lat2 = _to_float(lat2)
    lng2 = _to_float(lng2)

    # If any coord missing, make distance infinite so it won't be chosen
    if None in (lat1, lng1, lat2, lng2):
        return float("inf")

    R = 6_371_000.0  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def pick_warehouse(lat: Number, lng: Number):
    """Return the nearest active Warehouse with coordinates."""
    from .models import Warehouse  # local import avoids early app loading issues

    lat = _to_float(lat)
    lng = _to_float(lng)

    qs = Warehouse.objects.filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
    )

    chosen = None
    best = float("inf")
    for wh in qs.iterator():
        dist = _haversine(lat, lng, wh.latitude, wh.longitude)
        if dist < best:
            best = dist
            chosen = wh
    return chosen

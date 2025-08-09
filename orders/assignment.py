from math import radians, sin, cos, sqrt, atan2
from typing import Optional

from product_app.models import Warehouse


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371  # Earth radius km
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def pick_warehouse(lat: Optional[float], lng: Optional[float]):
    qs = Warehouse.objects.all()
    if lat is not None and lng is not None:
        best = None
        best_d = None
        for wh in qs:
            d = _haversine(lat, lng, wh.latitude, wh.longitude)
            if best_d is None or d < best_d:
                best_d = d
                best = wh
        if best:
            return best
    return qs.first()

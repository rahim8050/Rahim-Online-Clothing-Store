# orders/geo.py
from typing import Optional, Tuple, Iterable
from decimal import Decimal
import math

def _f(x) -> Optional[float]:
    return None if x is None or x == "" else float(x)

def normalize_latlng(lat, lng) -> Tuple[Optional[float], Optional[float]]:
    """
    Returns (lat, lng) as floats.
    If values look swapped (|lat|>90 and |lng|<=180), swap them.
    """
    lat, lng = _f(lat), _f(lng)
    if lat is None or lng is None:
        return None, None
    if abs(lat) > 90 and abs(lng) <= 180:
        lat, lng = lng, lat
    return lat, lng

def haversine_km(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    R = 6371.0
    dLat = math.radians(b_lat - a_lat)
    dLng = math.radians(b_lng - a_lng)
    s1 = (math.sin(dLat/2)**2 +
          math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) *
          math.sin(dLng/2)**2)
    return 2 * R * math.asin(math.sqrt(s1))

def best_orientation(lat, lng, refs: Iterable[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Choose between (lat,lng) and (lng,lat) by whichever is closer to the nearest ref point.
    refs: iterable of (lat,lng), e.g., warehouse coords.
    """
    a_lat, a_lng = normalize_latlng(lat, lng)
    b_lat, b_lng = normalize_latlng(lng, lat)
    if a_lat is None or a_lng is None:
        return b_lat, b_lng
    if b_lat is None or b_lng is None:
        return a_lat, a_lng
    def min_dist(p):
        return min(haversine_km(p[0], p[1], r[0], r[1]) for r in refs) if refs else 0.0
    return (a_lat, a_lng) if min_dist((a_lat, a_lng)) <= min_dist((b_lat, b_lng)) else (b_lat, b_lng)

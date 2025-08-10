import logging

from django.utils import timezone

from ..models import Order
from .geocoding import geocode_address

logger = logging.getLogger(__name__)


def ensure_order_coords(order: Order, *, force: bool = False) -> bool:
    """Ensure an order has latitude/longitude; return True if updated."""
    if not force and order.latitude is not None and order.longitude is not None:
        return False
    if not order.address:
        return False
    try:
        coords = geocode_address(order.address)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Geocode lookup failed: %s", exc)
        return False
    if not coords:
        return False
    lat, lng = coords
    order.latitude = lat
    order.longitude = lng
    order.coords_source = "geocode"
    order.coords_updated_at = timezone.now()
    order.save(update_fields=["latitude", "longitude", "coords_source", "coords_updated_at"])
    return True

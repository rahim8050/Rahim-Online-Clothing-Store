import logging
import time

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def _client() -> httpx.Client:
    return httpx.Client(timeout=settings.GEOCODING_TIMEOUT, follow_redirects=False)


def _geocode_geoapify(address: str) -> tuple[float, float] | None:
    api_key = getattr(settings, "GEOAPIFY_API_KEY", "")
    if not api_key:
        return None
    params = {"text": address, "apiKey": api_key}
    headers = {"User-Agent": settings.GEOCODING_USER_AGENT}
    for attempt in range(2):
        try:
            with _client() as client:
                resp = client.get(GEOAPIFY_URL, params=params, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("Geoapify request error: %s", exc)
            return None
        if resp.status_code == 429 and attempt == 0:
            time.sleep(1)
            continue
        if resp.status_code != 200:
            logger.warning("Geoapify response %s", resp.status_code)
            return None
        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning("Geoapify invalid JSON: %s", exc)
            return None
        features = data.get("features") or []
        if not features:
            return None
        feat = features[0]
        props = feat.get("properties", {})
        lat = props.get("lat")
        lon = props.get("lon")
        if lat is None or lon is None:
            coords = feat.get("geometry", {}).get("coordinates")
            if coords and len(coords) >= 2:
                lon, lat = coords[0], coords[1]
        if lat is not None and lon is not None:
            try:
                return float(lat), float(lon)
            except (TypeError, ValueError):
                return None
        return None
    return None


def _geocode_nominatim(address: str) -> tuple[float, float] | None:
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": settings.GEOCODING_USER_AGENT}
    for attempt in range(2):
        try:
            with _client() as client:
                resp = client.get(NOMINATIM_URL, params=params, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("Nominatim request error: %s", exc)
            return None
        if resp.status_code == 429 and attempt == 0:
            time.sleep(1)
            continue
        if resp.status_code != 200:
            logger.warning("Nominatim response %s", resp.status_code)
            return None
        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning("Nominatim invalid JSON: %s", exc)
            return None
        if not data:
            return None
        first = data[0]
        try:
            return float(first["lat"]), float(first["lon"])
        except (KeyError, TypeError, ValueError):
            return None
    return None


def geocode_address(address: str) -> tuple[float, float] | None:
    """Return (lat, lon) for address or None."""
    coords = _geocode_geoapify(address)
    if coords:
        return coords
    return _geocode_nominatim(address)

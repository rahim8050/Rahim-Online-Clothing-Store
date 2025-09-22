# yourapp/utils/geoapify.py
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model

logger = logging.getLogger(__name__)

# ---------- Geoapify ----------
def reverse_geocode(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Call Geoapify Reverse Geocoding API and return parsed JSON.
    Returns None on error or missing key.
    """
    api_key = getattr(settings, "GEOAPIFY_API_KEY", None)
    if not api_key:
        logger.warning("Geoapify API key missing (settings.GEOAPIFY_API_KEY).")
        return None

    url = "https://api.geoapify.com/v1/geocode/reverse"
    params = {"lat": lat, "lon": lon, "apiKey": api_key}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning("Geoapify reverse geocode failed: %s", e, exc_info=True)
        return None

# Optionally: a tiny helper to extract a nice label if present
def extract_formatted_address(payload: Dict[str, Any]) -> Optional[str]:
    try:
        feats = payload.get("features") or []
        if not feats:
            return None
        props = feats[0].get("properties", {})
        # Geoapify usually has 'formatted' or 'address_line1' + 'address_line2'
        return props.get("formatted") or props.get("address_line1")
    except Exception:
        return None

# ---------- Vendor field utility ----------
VENDOR_FIELDS = ["vendor", "owner", "user", "created_by"]

def get_vendor_field(model: type[Model]) -> str:
    for field in VENDOR_FIELDS:
        try:
            model._meta.get_field(field)
            return field
        except FieldDoesNotExist:
            continue
    logger.warning("No vendor FK field found on %s; defaulting to 'vendor'", model.__name__)
    return "vendor"

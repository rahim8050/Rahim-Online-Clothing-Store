# utils_payments_geo.py
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Union

import requests
from django.conf import settings

Q2 = Decimal("0.01")       # money to 2dp
Q6 = Decimal("0.000001")   # geo to 6dp

api_key = getattr(settings, "GEOAPIFY_API_KEY", None)


# -------------------- Geo --------------------
def reverse_geocode(
    lat: Union[float, str, Decimal],
    lon: Union[float, str, Decimal],
    *,
    timeout: int = 6,
    session: Optional[requests.Session] = None,
) -> dict:
    """
    Reverse geocode via Geoapify. Returns parsed JSON (dict) on success, or
    {'error': '...', 'status_code': <int>} on failure.
    """
    if not api_key:
        return {"error": "Geoapify API key missing in settings.GEOAPIFY_API_KEY", "status_code": 500}

    # normalize to 6 dp strings to avoid float artifacts
    lat_q = str(Decimal(str(lat)).quantize(Q6, rounding=ROUND_HALF_UP))
    lon_q = str(Decimal(str(lon)).quantize(Q6, rounding=ROUND_HALF_UP))

    url = "https://api.geoapify.com/v1/geocode/reverse"
    params = {"lat": lat_q, "lon": lon_q, "apiKey": api_key}
    headers = {"Accept": "application/json"}

    try:
        req = session.get if session else requests.get
        resp = req(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        return {
            "error": f"Failed to reverse geocode: {resp.status_code}",
            "status_code": resp.status_code,
            "body": _safe_json(resp),
        }
    except requests.RequestException as e:
        return {"error": f"Network error: {e.__class__.__name__}: {e}", "status_code": 0}


def _safe_json(resp: requests.Response) -> Optional[dict]:
    try:
        return resp.json()
    except Exception:
        return None


# -------------------- Money helpers --------------------
NumberLike = Union[str, int, float, Decimal]


def D(x: NumberLike) -> Decimal:
    """Safe Decimal constructor that preserves precision for strs and avoids float surprises."""
    return x if isinstance(x, Decimal) else Decimal(str(x))


def q2(x: NumberLike) -> Decimal:
    """Quantize to 2dp, HALF_UP (finance-friendly)."""
    return D(x).quantize(Q2, rounding=ROUND_HALF_UP)


def to_minor_units(amount: NumberLike) -> int:
    """Convert major currency units to minor (e.g., KES -> cents)."""
    return int((q2(amount) * 100).to_integral_value(rounding=ROUND_HALF_UP))


# -------------------- UI Status Normalizer --------------------
def derive_ui_payment_status(order: object, last_tx: Optional[object] = None) -> str:
    """
    Return a simple UI status: 'PAID', 'PENDING', 'FAILED', 'CANCELLED', 'REFUNDED', 'NOT_PAID'.

    Inputs are duck-typed:
      - order.paid (bool), order.payment_status (str-ish)
      - last_tx.status (str-ish), last_tx.callback_received (bool)
    """
    st = (getattr(order, "payment_status", "") or "").lower()
    is_paid_flag = bool(getattr(order, "paid", False))

    tx_status = ((getattr(last_tx, "status", "") or "").lower()) if last_tx else ""
    tx_cb = bool(getattr(last_tx, "callback_received", False)) if last_tx else False

    # Final paid
    if is_paid_flag or st in {"paid", "success"}:
        if tx_cb and tx_status in {"success", "refunded"}:
            return "PAID"
        # If gateway still pending callback, show PENDING to avoid confusing the user
        if tx_status in {"pending", "initialized", "unknown"} and not tx_cb:
            return "PENDING"
        return "PAID"

    # Unpaid paths
    if st in {"pending", "pending_confirmation", "initialized", "unknown"}:
        return "PENDING"
    if tx_status in {"pending", "initialized", "unknown"}:
        return "PENDING"
    if st == "failed" or tx_status == "failed":
        return "FAILED"
    if st == "cancelled" or tx_status == "cancelled":
        return "CANCELLED"
    if tx_status in {"refunded", "refunded_duplicate"}:
        return "REFUNDED"
    return "NOT_PAID"

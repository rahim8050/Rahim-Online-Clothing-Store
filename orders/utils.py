# utils_payments_geo.py
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import requests
from django.conf import settings

# ------------ Quantization constants ------------
Q6 = Decimal("0.000001")  # 6 dp (geo)
Q2 = Decimal("0.01")  # 2 dp (money)

# Cache once; safe if missing
api_key: str | None = getattr(settings, "GEOAPIFY_API_KEY", None)


# -------------------- Geo --------------------
def reverse_geocode(
    lat: float | str | Decimal,
    lon: float | str | Decimal,
    *,
    timeout: int = 6,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """
    Reverse geocode via Geoapify.

    Returns parsed JSON (dict) on success, or:
      {'error': '...', 'status_code': <int|None>, 'body': <json_or_text>}
    on failure.
    """
    if not api_key:
        return {
            "error": "Geoapify API key missing in settings.GEOAPIFY_API_KEY",
            "status_code": 500,
        }

    # Normalize to 6 dp strings to avoid float artifacts
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
        return {"error": f"HTTP error: {e.__class__.__name__}: {e}", "status_code": None}


def _safe_json(resp: requests.Response) -> Any:
    """Try json(); fall back to (trimmed) text."""
    try:
        return resp.json()
    except ValueError:
        txt = (resp.text or "").strip()
        return txt[:1000]  # avoid huge logs/UI payloads


# -------------------- Money helpers --------------------
def D(x: Any) -> Decimal:
    """Safe Decimal constructor."""
    return x if isinstance(x, Decimal) else Decimal(str(x))


def q2(x: Any) -> Decimal:
    """Quantize to 2 dp, HALF_UP."""
    return D(x).quantize(Q2, rounding=ROUND_HALF_UP)


def to_minor_units(amount: Any) -> int:
    """Convert a currency amount to minor units (e.g., KES cents)."""
    return int((q2(amount) * 100).to_integral_value(rounding=ROUND_HALF_UP))


# -------------------- UI Status Normalizer --------------------
def derive_ui_payment_status(order: Any, last_tx: Any | None = None) -> str:
    """
    Return a simple UI status:
      'PAID', 'PENDING', 'FAILED', 'CANCELLED', 'REFUNDED', 'NOT_PAID'.

    Uses Order fields (paid, payment_status) plus the latest Transaction when provided.
    """
    st = (getattr(order, "payment_status", "") or "").lower()
    tx_status = ((getattr(last_tx, "status", "") or "").lower()) if last_tx else ""
    tx_cb = bool(getattr(last_tx, "callback_received", False)) if last_tx else False

    # Final paid
    if getattr(order, "paid", False) or st in {"paid", "success"}:
        # Prefer PAID if callback verified with success/refunded
        if tx_cb and tx_status in {"success", "refunded"}:
            return "PAID"
        # If gateway looks pending and no callback yet, surface PENDING
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

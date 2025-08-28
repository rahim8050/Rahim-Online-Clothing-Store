import requests
from requests.structures import CaseInsensitiveDict
from django.conf import settings

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
Q2 = Decimal("0.01")

api_key = settings.GEOAPIFY_API_KEY


def reverse_geocode(lat, lon):
    url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={api_key}"

    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()  # Parsed JSON response
    else:
        return {
            "error": f"Failed to reverse geocode: {response.status_code}",
            "status_code": response.status_code,
        }






def D(x):  # safe Decimal
    return x if isinstance(x, Decimal) else Decimal(str(x))

def q2(x):  # 2dp HALF_UP
    return D(x).quantize(Q2, rounding=ROUND_HALF_UP)

def to_minor_units(amount) -> int:
    return int((q2(amount) * 100).to_integral_value(rounding=ROUND_HALF_UP))


# -------------------- UI Status Normalizer --------------------
def derive_ui_payment_status(order, last_tx: Optional[object] = None) -> str:
    """Return a simple UI status: 'PAID', 'PENDING', 'FAILED', 'CANCELLED', 'REFUNDED', 'NOT_PAID'.

    Uses Order fields (paid, payment_status) plus the latest Transaction when provided.
    """
    st = (getattr(order, "payment_status", "") or "").lower()
    tx_status = ((getattr(last_tx, "status", "") or "").lower()) if last_tx else ""
    tx_cb = bool(getattr(last_tx, "callback_received", False)) if last_tx else False

    # Final paid
    if order.paid or st in {"paid", "success"}:
        # If callback verified and success/refunded, mark as PAID; otherwise still treating as PAID for UI unless clearly pending
        if tx_cb and tx_status in {"success", "refunded"}:
            return "PAID"
        # Some gateways set paid only after verification; if we got here, prefer PAID unless explicitly pending
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

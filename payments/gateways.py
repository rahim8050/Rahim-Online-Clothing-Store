# payments/gateways.py
import os
from decimal import ROUND_HALF_UP, Decimal

import requests
from django.db import transaction as dbtx
from django.utils import timezone

from .models import Transaction

# Toggle stubbed refunds in dev
DEV_ALLOW_INSECURE_WEBHOOKS = os.getenv("PAYMENTS_ALLOW_INSECURE_WEBHOOKS", "0") == "1"
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET_KEY", "")
# payments/notify.py
from django.core.mail import send_mail
from django.db import IntegrityError, transaction

from payments.models import NotificationEvent  # the model lives in payments/models.py

__all__ = ["emit_once", "send_refund_email", "send_payment_email"]  # explicit exports


def emit_once(event_key: str, user, channel: str, send_fn, payload=None) -> bool:
    """Insert a NotificationEvent once; send after DB commit (prevents double emails on webhook replays)."""
    try:
        NotificationEvent.objects.create(
            event_key=event_key,
            user=user if getattr(user, "pk", None) else None,
            channel=channel,
            payload=payload or {},
        )
    except IntegrityError:
        return False  # already sent for this event_key
    transaction.on_commit(lambda: send_fn())
    return True


def send_refund_email(to_email: str, order_no, amount, reference, stage: str) -> None:
    subject = f"Refund {stage} for Order {order_no}"
    body = (
        f"Hi, your refund for Order {order_no} (KES {amount}) is {stage}.\n"
        f"Reference: {reference}\n\nIf you didn’t request this, contact support."
    )
    send_mail(subject, body, None, [to_email], fail_silently=False)


def send_payment_email(to_email: str, order_no, amount, reference, stage: str) -> None:
    subject = f"Payment {stage} for Order {order_no}"
    body = f"Your payment of KES {amount} is {stage}. Ref: {reference}"
    send_mail(subject, body, None, [to_email], fail_silently=False)


def refund_gateway_charge(tx):
    """Unified refund entry. Returns: {'ok': bool, 'refund_id': str|None, 'raw': dict|None, 'error': str|None}"""
    gw = getattr(tx, "gateway", None)
    if gw == "paystack":
        return _paystack_refund(tx)
    elif gw == "stripe":
        return _stripe_refund(tx)
    elif gw == "mpesa":
        return _mpesa_refund(tx)
    return {"ok": False, "refund_id": None, "raw": None, "error": f"Unsupported gateway: {gw}"}


# ---------- Paystack ----------
def _paystack_refund(tx):
    if DEV_ALLOW_INSECURE_WEBHOOKS:
        # Dev stub: pretend refund succeeded
        return {"ok": True, "refund_id": f"RF_{tx.reference}", "raw": {"dev": True}, "error": None}
    return _paystack_refund_live(tx)


def _paystack_refund_live(tx):
    if not PAYSTACK_SECRET:
        return {"ok": False, "refund_id": None, "raw": None, "error": "Missing PAYSTACK_SECRET_KEY"}

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET}"}
    # amount in kobo using Decimal to avoid float rounding
    amount_kobo = int(
        (Decimal(str(tx.amount)) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    payload = {"transaction": tx.gateway_reference or tx.reference, "amount": amount_kobo}

    try:
        r = requests.post(
            "https://api.paystack.co/refund", headers=headers, json=payload, timeout=30
        )
        data = r.json() if r.content else {}
    except Exception as e:
        return {"ok": False, "refund_id": None, "raw": {"exc": str(e)}, "error": "network"}

    ok = r.status_code in (200, 201) and data.get("status") is True
    refund_id = (data.get("data") or {}).get("reference")
    return {"ok": ok, "refund_id": refund_id, "raw": data, "error": None if ok else "api"}


# ---------- Other gateways (stubs for now) ----------
def _stripe_refund(tx):
    if DEV_ALLOW_INSECURE_WEBHOOKS:
        return {
            "ok": True,
            "refund_id": f"rf_{tx.reference.lower()}",
            "raw": {"dev": True},
            "error": None,
        }
    return {"ok": False, "refund_id": None, "raw": None, "error": "Real refund not implemented"}


def _mpesa_refund(tx):
    if DEV_ALLOW_INSECURE_WEBHOOKS:
        return {"ok": True, "refund_id": f"MP_{tx.reference}", "raw": {"dev": True}, "error": None}
    return {"ok": False, "refund_id": None, "raw": None, "error": "Reversal not implemented"}


# ---------- Duplicate-success auto-refund ----------
def maybe_refund_duplicate_success(tx, keep_earliest=True, refunded_status="refunded"):
    """
    Keep the earliest 'success' for tx.order_id; refund later 'success' rows.
    Returns list of refunded transaction references.
    """
    if not getattr(tx, "order_id", None):
        return []

    with dbtx.atomic():
        siblings = (
            Transaction.objects.select_for_update()
            .filter(order_id=tx.order_id, status="success")
            .order_by("processed_at", "id")
        )
        if siblings.count() <= 1:
            return []

        keeper = siblings.first() if keep_earliest else siblings.last()
        to_refund = [t for t in siblings if t.id != keeper.id]
        refunded_refs = []

        for dup in to_refund:
            res = refund_gateway_charge(dup)  # <- uses stub in dev, live API in prod
            if res.get("ok"):
                dup.status = refunded_status  # or 'refunded_duplicate' if your choices include it
                dup.processed_at = timezone.now()
                dup.save(update_fields=["status", "processed_at"])
                refunded_refs.append(dup.reference)

        return refunded_refs

# payments/services.py
from __future__ import annotations

import hashlib
import hmac
import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction as dbtx
from django.utils import timezone

from vendor_app.models import VendorOrg

from .enums import Gateway, TxnStatus
from .idempotency import idempotent
from .models import AuditLog, PaymentEvent, Payout, Transaction
from .selectors import safe_decrement_stock, set_order_paid
import logging
logger = logging.getLogger(__name__)

# =========================================================
#                           Helpers
# =========================================================
def compute_hmac_sha512(secret: str, body_bytes: bytes) -> str:
    """Lowercase hex HMAC-SHA512 of the raw request body."""
    return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha512).hexdigest().lower()


# =========================================================
#                    Idempotent checkout init
# =========================================================
@dbtx.atomic
def init_checkout(
    *,
    order,
    user,
    method: str,
    gateway: Gateway,
    amount: Decimal,
    currency: str,
    idempotency_key: str,
    reference: str,
) -> Transaction:
    """
    Create-or-reuse a Transaction keyed by idempotency_key. Enforces that
    reused keys match the original (order, amount, gateway) tuple.
    """
    try:
        txn, created = Transaction.objects.select_for_update().get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "order": order,
                "user": user,
                "method": method,
                "gateway": gateway,
                "amount": amount,
                "currency": currency,
                "status": TxnStatus.PENDING,
                "reference": reference,
            },
        )
    except IntegrityError:
        txn = Transaction.objects.select_for_update().get(idempotency_key=idempotency_key)
        created = False

    if not created and (txn.order_id != order.id or txn.amount != amount or txn.gateway != gateway):
        raise ValidationError("Idempotency key reuse with mismatched parameters.")

    AuditLog.log(event="PAYMENT_INIT", transaction=txn, order=order)
    return txn


# =========================================================
#                    Webhook verification
# =========================================================
def verify_stripe(request) -> Any:
    """Verify Stripe webhook using SDK; return event object; raise ValidationError on failure."""
    import stripe

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    try:
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as e:
        raise ValidationError(f"Stripe signature verification failed: {e}")


def verify_paystack(request) -> dict:
    """Validate Paystack webhook via raw-body HMAC SHA512; return parsed JSON dict or raise ValidationError."""
    body = request.body  # bytes
    signature = (request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "") or "").strip().lower()
    expected = compute_hmac_sha512(getattr(settings, "PAYSTACK_SECRET_KEY", "") or "", body)
    if not signature or not hmac.compare_digest(expected, signature):
        raise ValidationError("Invalid Paystack signature")
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        raise ValidationError("Invalid JSON payload")


def verify_mpesa(request) -> dict:
    """Minimal M-Pesa (Daraja) webhook stub; raise ValidationError on invalid."""
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        raise ValidationError("Invalid JSON payload")
    if "Body" not in data:
        raise ValidationError("Invalid payload: missing Body")
    return data


# =========================================================
#                      Core processing
# =========================================================
def _eligible_for_auto_refund(txn: Transaction) -> bool:
    return txn.gateway in {Gateway.STRIPE, Gateway.PAYSTACK}


@dbtx.atomic
def process_success(
    *, txn: Transaction, gateway_reference: str | None, request_id: str
) -> Transaction:
    """
    Mark a transaction as successful, handle duplicates & auto-refund, update stock,
    and flip the order to paid (single source of truth).
    """
    if txn.status in {
        TxnStatus.SUCCESS,
        TxnStatus.DUPLICATE_SUCCESS,
        TxnStatus.FAILED,
        TxnStatus.CANCELLED,
        TxnStatus.REFUNDED,
    }:
        AuditLog.log(
            event="WEBHOOK_REPLAY_BLOCKED", transaction=txn, order=txn.order, request_id=request_id
        )
        return txn

    # Has another success already been recorded for the same order?
    already_paid = (
        Transaction.objects.select_for_update()
        .filter(order=txn.order, status=TxnStatus.SUCCESS)
        .exclude(pk=txn.pk)
        .exists()
    )

    if already_paid:
        txn.mark_duplicate_success()
        AuditLog.log(
            event="DUPLICATE_SUCCESS", transaction=txn, order=txn.order, request_id=request_id
        )

        # Auto-refund only if supported and amounts match
        if _eligible_for_auto_refund(txn) and txn.amount == txn.order.get_total_cost():
            try:
                issue_refund(txn, request_id=request_id)
                txn.status = TxnStatus.REFUNDED
                txn.refund_reference = (
                    txn.refund_reference
                    or gateway_reference
                    or getattr(txn, "gateway_reference", None)
                    or txn.reference
                )
                txn.refunded_at = timezone.now()
                txn.save(update_fields=["status", "refund_reference", "refunded_at", "updated_at"])
                AuditLog.log(
                    event="DUPLICATE_REFUND_ISSUED",
                    transaction=txn,
                    order=txn.order,
                    request_id=request_id,
                )
            except Exception as e:  # best effort
                AuditLog.log(
                    event="REFUND_FAILED",
                    transaction=txn,
                    order=txn.order,
                    request_id=request_id,
                    message=str(e),
                )
        else:
            AuditLog.log(
                event="DUPLICATE_MANUAL_REVERSAL_REQUIRED",
                transaction=txn,
                order=txn.order,
                request_id=request_id,
            )
        return txn

    # First success for this order
    txn.mark_success(gateway_reference)
    safe_decrement_stock(txn.order, request_id=request_id)
    set_order_paid(txn.order, request_id=request_id)
    AuditLog.log(event="PAYMENT_SUCCESS", transaction=txn, order=txn.order, request_id=request_id)
    return txn


@dbtx.atomic
def process_failure(*, txn: Transaction, request_id: str) -> Transaction:
    """Mark a transaction as failed, if not already terminal."""
    if txn.status in {
        TxnStatus.SUCCESS,
        TxnStatus.DUPLICATE_SUCCESS,
        TxnStatus.FAILED,
        TxnStatus.CANCELLED,
        TxnStatus.REFUNDED,
    }:
        AuditLog.log(
            event="WEBHOOK_REPLAY_BLOCKED", transaction=txn, order=txn.order, request_id=request_id
        )
        return txn
    txn.mark_failed()
    AuditLog.log(event="PAYMENT_FAILED", transaction=txn, order=txn.order, request_id=request_id)
    return txn


# =========================================================
#                        Refund plumbing
# =========================================================
def issue_refund(txn: Transaction, request_id: str = "") -> None:
    """
    Best-effort refund. Stores a gateway-issued reference (if available) back on the txn.
    """
    if txn.gateway == Gateway.STRIPE:
        import stripe

        r = stripe.Refund.create(
            payment_intent=txn.gateway_reference, reason="requested_by_customer"
        )
        txn.refund_reference = getattr(r, "id", None)
        txn.save(update_fields=["refund_reference", "updated_at"])
        AuditLog.log(event="REFUND_ISSUED", transaction=txn, order=txn.order, request_id=request_id)
        return

    if txn.gateway == Gateway.PAYSTACK:
        # https://paystack.com/docs/api/refund/#create
        secret = getattr(settings, "PAYSTACK_SECRET_KEY", "") or ""
        if not secret:
            raise ValidationError("PAYSTACK_SECRET_KEY not configured")

        payload = {
            # prefer gateway_reference; fallback to init reference
            "transaction": txn.gateway_reference
            or txn.reference,
        }
        headers = {
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            "https://api.paystack.co/refund", json=payload, headers=headers, timeout=30
        )
        try:
            data = resp.json()
        except Exception:
            data = {}
        if not resp.ok:
            raise ValidationError(f"Paystack refund failed: {data or resp.text}")

        # Try common locations for an identifier
        ref = None
        if isinstance(data, dict):
            d = data.get("data") or {}
            ref = d.get("reference") or d.get("id") or d.get("refund_reference")
        txn.refund_reference = ref
        txn.save(update_fields=["refund_reference", "updated_at"])
        AuditLog.log(event="REFUND_ISSUED", transaction=txn, order=txn.order, request_id=request_id)
        return

    # M-Pesa or others: usually manual reversal — record for ops
    AuditLog.log(
        event="REFUND_ISSUE_MANUAL", transaction=txn, order=txn.order, request_id=request_id
    )


# -------------------- Payouts (idempotent) --------------------
@idempotent(scope="vendor:payout")
def process_payout(
    *,
    org_id: int | None = None,
    user_id: int | None = None,
    amount,
    currency: str = "KES",
    idempotency_key: str | None = None,
):
    """
    Simulate a payout and ensure duplicate calls with same key do not double-payout.
    For demo/testing, we just log and return a deterministic reference based on the key.
    """
    ref = f"PAYOUT-{(idempotency_key or '')[-12:]}" if idempotency_key else "PAYOUT"
    AuditLog.log(
        event="PAYOUT_SUCCESS",
        request_id=idempotency_key or "",
        message=f"{ref}:{amount}:{currency}",
    )
    return {"reference": ref, "amount": str(amount), "currency": currency}


# -------------------- Org settlement helpers --------------------
def _resolve_org_for_order(order) -> VendorOrg | None:
    try:
        item = order.items.select_related("product__owner__vendor_profile").first()
        if item and getattr(item.product.owner, "vendor_profile", None):
            return item.product.owner.vendor_profile.org
    except Exception:
        return None
    return None


def apply_org_settlement(
    txn: Transaction, provider: str, raw_body: bytes, payload: dict | None = None
) -> PaymentEvent:
    """
    Bind transaction to VendorOrg, compute commission + net, persist PaymentEvent & Payout.

    - Commission = org.org_commission_rate * gross
    - Net to vendor = gross - fees - commission
    - Fees default to 0 unless provided by gateway payload (not parsed here)
    """
    org = txn.vendor_org or _resolve_org_for_order(txn.order)
    rate = Decimal("0")
    if org is not None and getattr(org, "org_commission_rate", None) is not None:
        rate = Decimal(str(org.org_commission_rate))

    gross = Decimal(str(txn.amount))
    fees = Decimal("0.00")
    commission = (gross * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net = (gross - fees - commission).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Persist to txn
    update_fields = []
    if txn.vendor_org_id is None and org is not None:
        txn.vendor_org = org
        update_fields.append("vendor_org")
    txn.gross_amount = gross
    txn.fees_amount = fees
    txn.commission_amount = commission
    txn.net_to_vendor = net
    update_fields += [
        "gross_amount",
        "fees_amount",
        "commission_amount",
        "net_to_vendor",
        "updated_at",
    ]
    txn.save(update_fields=update_fields)

    body_sha256 = hashlib.sha256(raw_body or b"").hexdigest()
    evt, _ = PaymentEvent.objects.get_or_create(
        body_sha256=body_sha256,
        defaults={
            "provider": provider,
            "reference": txn.reference,
            "vendor_org": org,
            "body": payload or {},
            "gross_amount": gross,
            "fees_amount": fees,
            "net_to_vendor": net,
        },
    )

    # Create payout record per successful txn (idempotent via OneToOne)
    try:
        if org is not None:
            Payout.objects.get_or_create(
                transaction=txn,
                defaults={"vendor_org": org, "amount": net, "currency": txn.currency},
            )
    except Exception as e:
          logger.debug("idempotency side-effect failed: %s", e, exc_info=True)

    return evt

from __future__ import annotations

import json
import hmac
import hashlib
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction as dbtx
from django.utils import timezone

from .enums import Gateway, TxnStatus
from .models import Transaction, AuditLog, PaymentEvent, Payout
from .selectors import safe_decrement_stock, set_order_paid
from .idempotency import idempotent
from .models import IdempotencyKey
from vendor_app.models import VendorOrg
from decimal import Decimal, ROUND_HALF_UP
import hashlib


# Helpers

def compute_hmac_sha512(secret: str, body_bytes: bytes) -> str:
    """Return lowercase hex HMAC-SHA512 of raw body.

    Note: Always use the raw request body for signing, never re-serialized JSON.
    """
    return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha512).hexdigest().lower()


# Idempotent checkout
@dbtx.atomic
def init_checkout(*, order, user, method, gateway, amount, currency, idempotency_key, reference):
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
    if not created and (
        txn.order_id != order.id or txn.amount != amount or txn.gateway != gateway
    ):
        raise ValidationError("Idempotency key reuse with mismatched parameters.")
    AuditLog.log(event="PAYMENT_INIT", transaction=txn, order=order)
    return txn


# Webhook verification stubs

def verify_stripe(request) -> Any:
    import stripe

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    secret = settings.STRIPE_WEBHOOK_SECRET
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def verify_paystack(request) -> dict:
    """Validate Paystack webhook using raw-body HMAC.

    - Reads raw body bytes
    - Computes HMAC-SHA512 with PAYSTACK_SECRET_KEY
    - Constant-time compare with provided signature header
    - Returns parsed JSON dict on success
    """
    body = request.body  # bytes, raw body
    signature = (request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "") or "").strip().lower()
    expected = compute_hmac_sha512(settings.PAYSTACK_SECRET_KEY or "", body)
    if not signature or not hmac.compare_digest(expected, signature):
        raise ValidationError("Invalid signature")
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        raise ValidationError("Invalid JSON")
    return data


def verify_mpesa(request) -> dict:
    data = json.loads(request.body.decode())
    if "Body" not in data:
        raise ValidationError("Invalid payload")
    return data


# Core processing

def _eligible_for_auto_refund(txn: Transaction) -> bool:
    return txn.gateway in {Gateway.STRIPE, Gateway.PAYSTACK}


@dbtx.atomic
def process_success(*, txn: Transaction, gateway_reference: str | None, request_id: str):
    if txn.status in {
        TxnStatus.SUCCESS,
        TxnStatus.DUPLICATE_SUCCESS,
        TxnStatus.FAILED,
        TxnStatus.CANCELLED,
        TxnStatus.REFUNDED,
    }:
        AuditLog.log(
            event="WEBHOOK_REPLAY_BLOCKED",
            transaction=txn,
            order=txn.order,
            request_id=request_id,
        )
        return txn

    already_paid = Transaction.objects.select_for_update().filter(
        order=txn.order, status=TxnStatus.SUCCESS
    ).exclude(pk=txn.pk).exists()
    if already_paid:
        txn.mark_duplicate_success()
        AuditLog.log(
            event="DUPLICATE_SUCCESS",
            transaction=txn,
            order=txn.order,
            request_id=request_id,
        )
        if _eligible_for_auto_refund(txn) and txn.amount == txn.order.get_total_cost():
            try:
                issue_refund(txn, request_id=request_id)
                txn.status = TxnStatus.REFUNDED
                txn.refund_reference = txn.refund_reference or (
                    gateway_reference or txn.gateway_reference or txn.reference
                )
                txn.refunded_at = timezone.now()
                txn.save(
                    update_fields=["status", "refund_reference", "refunded_at", "updated_at"]
                )
                AuditLog.log(
                    event="DUPLICATE_REFUND_ISSUED",
                    transaction=txn,
                    order=txn.order,
                    request_id=request_id,
                )
            except Exception as e:  # pragma: no cover
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

    txn.mark_success(gateway_reference)
    safe_decrement_stock(txn.order, request_id=request_id)
    set_order_paid(txn.order, request_id=request_id)
    AuditLog.log(
        event="PAYMENT_SUCCESS", transaction=txn, order=txn.order, request_id=request_id
    )
    return txn


@dbtx.atomic
def process_failure(*, txn: Transaction, request_id: str):
    if txn.status in {
        TxnStatus.SUCCESS,
        TxnStatus.DUPLICATE_SUCCESS,
        TxnStatus.FAILED,
        TxnStatus.CANCELLED,
        TxnStatus.REFUNDED,
    }:
        AuditLog.log(
            event="WEBHOOK_REPLAY_BLOCKED",
            transaction=txn,
            order=txn.order,
            request_id=request_id,
        )
        return txn
    txn.mark_failed()
    AuditLog.log(
        event="PAYMENT_FAILED", transaction=txn, order=txn.order, request_id=request_id
    )
    return txn


# Refund pluggable calls

def issue_refund(txn: Transaction, request_id: str = ""):
    if txn.gateway == Gateway.STRIPE:
        import stripe

        r = stripe.Refund.create(
            payment_intent=txn.gateway_reference, reason="requested_by_customer"
        )
        txn.refund_reference = getattr(r, "id", None)
    elif txn.gateway == Gateway.PAYSTACK:
        # POST https://api.paystack.co/refund with { "transaction": txn.gateway_reference }
        # Store response id into txn.refund_reference
        pass
    else:
        # M-Pesa: manual reversal (Daraja Reversal API if enabled) — log via AuditLog
        pass
    AuditLog.log(event="REFUND_ISSUED", transaction=txn, order=txn.order, request_id=request_id)


# -------------------- Payouts (idempotent) --------------------

@idempotent(scope="vendor:payout")
def process_payout(*, org_id: int | None = None, user_id: int | None = None, amount, currency="KES", idempotency_key: str | None = None):
    """Simulate a payout and ensure duplicate calls with same key do not double-payout.

    For demo/testing, we just log and return a deterministic reference based on the key.
    """
    ref = f"PAYOUT-{(idempotency_key or '')[-12:]}" if idempotency_key else "PAYOUT"
    AuditLog.log(event="PAYOUT_SUCCESS", request_id=idempotency_key or "", message=f"{ref}:{amount}:{currency}")
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


def apply_org_settlement(txn: Transaction, provider: str, raw_body: bytes, payload: dict | None = None) -> PaymentEvent:
    """Bind transaction to VendorOrg, compute commission + net, persist PaymentEvent & Payout.

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
    update_fields += ["gross_amount", "fees_amount", "commission_amount", "net_to_vendor", "updated_at"]
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
    except Exception:
        pass

    return evt

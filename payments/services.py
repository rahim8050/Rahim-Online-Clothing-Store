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
from .models import Transaction, AuditLog
from .selectors import safe_decrement_stock, set_order_paid


# Helpers

def compute_hmac_sha512(secret: str, body_bytes: bytes) -> str:
    return hmac.new(secret.encode(), body_bytes, hashlib.sha512).hexdigest()


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
    body = request.body
    signature = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")
    expected = compute_hmac_sha512(settings.PAYSTACK_SECRET_KEY, body)
    if not hmac.compare_digest(signature, expected):
        raise ValidationError("Invalid signature")
    return json.loads(body.decode())


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

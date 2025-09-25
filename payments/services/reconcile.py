from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import requests
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from payments.enums import Gateway, TxnStatus
from payments.models import ReconcileIdempotency, Transaction

from . import process_failure, process_success

logger = logging.getLogger(__name__)


class ReconcileError(Exception):
    """Base exception for reconciliation failures."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.extra = extra or {}


class ReconcileConflict(ReconcileError):
    """Raised when reconciliation cannot proceed due to current gateway state."""

    def __init__(
        self, code: str, message: str, *, extra: dict[str, Any] | None = None
    ) -> None:
        super().__init__(code=code, message=message, status_code=409, extra=extra)


@dataclass(frozen=True)
class VerifyResult:
    status: str
    reference: str | None
    raw: dict[str, Any]


def reconcile_paystack(tx_reference: str) -> dict[str, Any]:
    if not tx_reference:
        raise ReconcileError("missing_reference", "Transaction reference is required.")

    txn = _get_transaction_for_ref(tx_reference, Gateway.PAYSTACK)
    verify = _fetch_paystack_status(txn, tx_reference)
    key = _build_idempotency_key(txn, verify.reference or tx_reference)

    if verify.status == "success":
        summary = _finalize_success(txn, verify, key)
        return summary

    if verify.status == "failed":
        _register_failure(txn, verify, key)
        _metric("reconcile_failure", gateway=txn.gateway, reason="gateway_failed")
        raise ReconcileConflict(
            code="gateway_failed",
            message="Paystack reports this transaction as failed.",
            extra={
                "gateway": txn.gateway,
                "reference": txn.reference,
                "provider_status": verify.status,
            },
        )

    if verify.status == "pending":
        _metric("reconcile_pending", gateway=txn.gateway)
        raise ReconcileConflict(
            code="gateway_pending",
            message="Paystack still marks this transaction as pending.",
            extra={
                "gateway": txn.gateway,
                "reference": txn.reference,
                "provider_status": verify.status,
            },
        )

    _metric("reconcile_error", gateway=txn.gateway, code=verify.status)
    raise ReconcileError(
        code="gateway_error",
        message="Unable to reconcile Paystack transaction (unexpected status).",
        status_code=502,
        extra={
            "gateway": txn.gateway,
            "reference": txn.reference,
            "provider_status": verify.status,
        },
    )


def reconcile_mpesa(checkout_id: str) -> dict[str, Any]:
    _metric("reconcile_unsupported", gateway=Gateway.MPESA.value)
    raise ReconcileError(
        code="gateway_not_supported",
        message="M-Pesa reconcile is not yet implemented.",
        status_code=501,
        extra={"gateway": Gateway.MPESA.value},
    )


def reconcile_stripe(session_id: str) -> dict[str, Any]:
    _metric("reconcile_unsupported", gateway=Gateway.STRIPE.value)
    raise ReconcileError(
        code="gateway_not_supported",
        message="Stripe reconcile is not yet implemented.",
        status_code=501,
        extra={"gateway": Gateway.STRIPE.value},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _finalize_success(
    txn: Transaction, verify: VerifyResult, key: str
) -> dict[str, Any]:
    with transaction.atomic():
        record, _ = ReconcileIdempotency.objects.select_for_update().get_or_create(
            key=key,
            defaults={"result_json": {}, "executed_at": None},
        )

        if record.executed_at and record.result_json:
            cached_payload = dict(record.result_json)
            cached_payload["cached"] = True
            _metric("reconcile_cached", gateway=txn.gateway)
            logger.info(
                "payments.reconcile.cached",
                extra={
                    "gateway": txn.gateway,
                    "reference": txn.reference,
                    "transaction_id": txn.pk,
                },
            )
            return cached_payload

        locked_txn = (
            Transaction.objects.select_for_update()
            .select_related("order", "order__user", "vendor_org")
            .get(pk=txn.pk)
        )
        order = locked_txn.order
        paid_before = getattr(order, "paid", False)
        stock_before = getattr(order, "stock_updated", False)
        previous_status = locked_txn.status

        try:
            locked_txn = process_success(
                txn=locked_txn, gateway_reference=verify.reference, request_id=key
            )
        except ValidationError as exc:
            _metric(
                "reconcile_failure", gateway=locked_txn.gateway, reason="stock_conflict"
            )
            logger.warning(
                "payments.reconcile.stock_conflict",
                extra={
                    "gateway": locked_txn.gateway,
                    "reference": locked_txn.reference,
                },
            )
            raise ReconcileConflict("stock_conflict", str(exc)) from exc

        order.refresh_from_db(fields=["paid", "payment_status", "stock_updated"])
        paid_changed = (not paid_before) and getattr(order, "paid", False)
        stock_changed = (not stock_before) and getattr(order, "stock_updated", False)

        summary = _build_summary(
            locked_txn,
            order,
            verify,
            key,
            duplicate=(previous_status == TxnStatus.SUCCESS),
            stock_changed=stock_changed,
            paid_changed=paid_changed,
        )
        _store_result(record, summary)

        user_id = getattr(order, "user_id", None)
        vendor_owner_id = getattr(
            getattr(locked_txn, "vendor_org", None), "owner_id", None
        )
        transaction.on_commit(
            lambda: _emit_events(user_id, vendor_owner_id, summary, cached=False)
        )

    _metric(
        "reconcile_success",
        gateway=txn.gateway,
        duplicate=summary.get("duplicate", False),
    )
    logger.info(
        "payments.reconcile.success",
        extra={
            "gateway": txn.gateway,
            "reference": txn.reference,
            "transaction_id": txn.pk,
            "duplicate": summary.get("duplicate", False),
        },
    )
    summary_with_flag = dict(summary)
    summary_with_flag["cached"] = False
    return summary_with_flag


def _register_failure(txn: Transaction, verify: VerifyResult, key: str) -> None:
    with transaction.atomic():
        locked_txn = (
            Transaction.objects.select_for_update()
            .select_related("order", "order__user", "vendor_org")
            .get(pk=txn.pk)
        )
        previous_status = locked_txn.status
        locked_txn = process_failure(txn=locked_txn, request_id=key)
        order = locked_txn.order
        order.refresh_from_db(fields=["paid", "payment_status", "stock_updated"])
        user_id = getattr(order, "user_id", None)
        vendor_owner_id = getattr(
            getattr(locked_txn, "vendor_org", None), "owner_id", None
        )
        summary = {
            "ok": False,
            "status": locked_txn.status,
            "gateway": locked_txn.gateway,
            "reference": locked_txn.reference,
            "transaction_id": locked_txn.pk,
            "order_id": order.pk,
            "duplicate": previous_status == TxnStatus.SUCCESS,
            "effects": {
                "stock_decremented": False,
                "order_marked_paid": getattr(order, "paid", False),
            },
            "transaction": {
                "status": locked_txn.status,
                "amount": str(locked_txn.amount),
                "currency": locked_txn.currency,
                "processed_at": _iso(locked_txn.processed_at),
                "gateway_reference": locked_txn.gateway_reference,
            },
            "order": {
                "paid": getattr(order, "paid", False),
                "payment_status": getattr(order, "payment_status", ""),
                "stock_updated": getattr(order, "stock_updated", False),
            },
            "provider": {
                "status": verify.status,
                "reference": verify.reference,
                "raw": _prune_payload(verify.raw),
            },
        }
        transaction.on_commit(
            lambda: _emit_events(user_id, vendor_owner_id, summary, cached=False)
        )

    logger.info(
        "payments.reconcile.gateway_failed",
        extra={
            "gateway": txn.gateway,
            "reference": txn.reference,
            "transaction_id": txn.pk,
        },
    )


def _get_transaction_for_ref(ref: str, gateway: Gateway) -> Transaction:
    filters = Q(reference__iexact=ref) | Q(gateway_reference__iexact=ref)
    txn = (
        Transaction.objects.select_related("order", "order__user", "vendor_org")
        .filter(filters, gateway=gateway)
        .order_by("-created_at")
        .first()
    )
    if txn is None:
        raise ReconcileError(
            "transaction_not_found",
            f"No {gateway.value} transaction found for reference '{ref}'.",
            status_code=404,
            extra={"gateway": gateway.value, "reference": ref},
        )
    return txn


def _fetch_paystack_status(txn: Transaction, reference: str) -> VerifyResult:
    secret = getattr(settings, "PAYSTACK_SECRET_KEY", "")
    if not secret:
        raise ReconcileError(
            "paystack_secret_missing",
            "PAYSTACK_SECRET_KEY is not configured.",
            status_code=500,
            extra={"gateway": txn.gateway},
        )

    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {secret}", "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise ReconcileError(
            "paystack_network_error",
            f"Verification request failed: {exc}",
            status_code=502,
            extra={"gateway": txn.gateway, "reference": reference},
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ReconcileError(
            "paystack_invalid_json",
            "Paystack returned invalid JSON.",
            status_code=502,
            extra={"gateway": txn.gateway, "reference": reference},
        ) from exc

    data = payload.get("data") or {}
    status_str = str(data.get("status") or "").lower()
    gateway_ref = (
        data.get("reference") or data.get("id") or txn.gateway_reference or reference
    )

    if response.status_code >= 500:
        raise ReconcileError(
            "paystack_unavailable",
            f"Paystack responded with status {response.status_code}.",
            status_code=502,
            extra={"gateway": txn.gateway, "reference": reference},
        )

    if status_str == "success":
        return VerifyResult(status="success", reference=str(gateway_ref), raw=payload)

    if status_str in {"failed", "abandoned", "error"}:
        return VerifyResult(status="failed", reference=str(gateway_ref), raw=payload)

    if status_str in {"ongoing", "pending", "reversed"}:
        return VerifyResult(status="pending", reference=str(gateway_ref), raw=payload)

    # Default to error for unknown states
    return VerifyResult(status="error", reference=str(gateway_ref), raw=payload)


def _build_summary(
    txn: Transaction,
    order,
    verify: VerifyResult,
    key: str,
    *,
    duplicate: bool,
    stock_changed: bool,
    paid_changed: bool,
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": txn.status,
        "gateway": txn.gateway,
        "reference": txn.reference,
        "transaction_id": txn.pk,
        "order_id": order.pk,
        "idempotency_key": key,
        "duplicate": duplicate,
        "effects": {
            "stock_decremented": bool(stock_changed),
            "order_marked_paid": bool(paid_changed or getattr(order, "paid", False)),
        },
        "transaction": {
            "status": txn.status,
            "amount": str(txn.amount),
            "currency": txn.currency,
            "processed_at": _iso(txn.processed_at),
            "gateway_reference": txn.gateway_reference,
        },
        "order": {
            "paid": getattr(order, "paid", False),
            "payment_status": getattr(order, "payment_status", ""),
            "stock_updated": getattr(order, "stock_updated", False),
        },
        "provider": {
            "status": verify.status,
            "reference": verify.reference,
            "raw": _prune_payload(verify.raw),
        },
    }


def _store_result(record: ReconcileIdempotency, summary: dict[str, Any]) -> None:
    payload = dict(summary)
    payload.pop("cached", None)
    record.result_json = payload
    record.executed_at = timezone.now()
    record.save(update_fields=["result_json", "executed_at", "updated_at"])


def _emit_events(
    user_id: int | None,
    vendor_owner_id: int | None,
    summary: dict[str, Any],
    *,
    cached: bool,
) -> None:
    payload = {
        "type": "payments.reconciled",
        "cached": cached,
        "gateway": summary.get("gateway"),
        "reference": summary.get("reference"),
        "transaction": summary.get("transaction"),
        "order": summary.get("order"),
        "effects": summary.get("effects"),
        "duplicate": summary.get("duplicate", False),
        "status": summary.get("status"),
    }
    if user_id:
        try:
            from notifications.ws import push_to_user

            push_to_user(int(user_id), payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("payments.reconcile.push_user_failed: %s", exc, exc_info=True)
    if vendor_owner_id:
        try:
            layer = get_channel_layer()
            if layer:
                async_to_sync(layer.group_send)(
                    f"vendor.{int(vendor_owner_id)}",
                    {
                        "type": "vendor.event",
                        "t": "payments.reconciled",
                        "payload": payload,
                    },
                )
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(
                "payments.reconcile.push_vendor_failed: %s", exc, exc_info=True
            )


def _build_idempotency_key(txn: Transaction, reference_hint: str | None) -> str:
    base = reference_hint or txn.gateway_reference or txn.reference
    return f"{txn.gateway}:{txn.order_id}:{base}"


def _metric(name: str, **labels: Any) -> None:
    try:
        logger.info("metric.payments.%s %s", name, labels)
    except Exception:  # pragma: no cover - defensive
        pass


def _iso(value) -> str | None:
    if value is None:
        return None
    try:
        return value.isoformat()
    except Exception:
        return None


def _prune_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    try:
        data = json.dumps(payload)
    except (TypeError, ValueError):
        return {}
    if len(data) > 4000:
        return {}
    return payload

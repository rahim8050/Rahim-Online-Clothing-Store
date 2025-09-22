# payments/views.py
from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction as dbtx
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from payments.notify import emit_once, send_payment_email, send_refund_email

from .enums import TxnStatus
from .idempotency import accept_once
from .models import AuditLog, Transaction
from .services import (
    apply_org_settlement,
    init_checkout,
    process_failure,
    process_success,
    verify_mpesa,
    verify_paystack,
    verify_stripe,
)


# ---------------------------
# Checkout (session required)
# ---------------------------
@method_decorator(login_required, name="dispatch")
@method_decorator(csrf_exempt, name="dispatch")  # API-style: session-auth + CSRF exempt
class CheckoutView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

        required = ["order_id", "amount", "currency", "gateway", "method", "idempotency_key"]
        for key in required:
            if key not in data:
                return JsonResponse({"ok": False, "error": f"missing_{key}"}, status=400)

        from orders.models import Order

        order = get_object_or_404(Order, pk=data["order_id"], user=request.user)

        # Strict amount check (Decimal)
        amount = Decimal(str(data["amount"]))
        if amount != order.get_total_cost():
            return JsonResponse({"ok": False, "error": "amount_mismatch"}, status=400)

        reference = f"ORD-{order.id}-{uuid.uuid4().hex[:8]}"

        txn = init_checkout(
            order=order,
            user=request.user,
            method=data["method"],
            gateway=data["gateway"],
            amount=amount,
            currency=data["currency"],
            idempotency_key=data["idempotency_key"],
            reference=reference,
        )

        return JsonResponse(
            {
                "ok": True,
                "reference": txn.reference,
                "gateway": txn.gateway,
                "next_action": {},  # populate per-gateway init instructions if needed
            }
        )


# ---------------------------
# Stripe Webhook
# ---------------------------
@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        request_id = hashlib.sha256(request.body).hexdigest()[:16]

        # 1) Verify Stripe signature → parsed event (raises on invalid)
        try:
            event = verify_stripe(request)
        except ValidationError as e:
            AuditLog.log(event="WEBHOOK_SIGNATURE_INVALID", request_id=request_id, message=str(e))
            return JsonResponse({"ok": False}, status=400)

        # 2) Idempotency (provider retries)
        if not accept_once(scope="webhook:stripe", request=request):
            return HttpResponse(status=200)

        event_type = event.get("type")
        obj = (event.get("data") or {}).get("object", {}) or {}

        # Prefer explicit reference (metadata / client_reference_id)
        reference = (obj.get("metadata") or {}).get("reference") or obj.get("client_reference_id")

        # For success, capture gateway payment intent id
        payment_intent = obj.get("payment_intent") or obj.get("id")

        # 3) Resolve and process transaction
        with dbtx.atomic():
            txn = None
            if reference:
                try:
                    txn = Transaction.objects.select_for_update().get(reference=reference)
                except Transaction.DoesNotExist:
                    txn = None

            if txn is None and payment_intent:
                # Fallback if you store gateway reference on the txn
                try:
                    txn = Transaction.objects.select_for_update().get(
                        gateway_reference=payment_intent
                    )
                except Transaction.DoesNotExist:
                    txn = None

            if txn is None:
                AuditLog.log(
                    event="WEBHOOK_UNKNOWN_REFERENCE",
                    request_id=request_id,
                    meta={"reference": reference, "gateway_ref": payment_intent},
                )
                return JsonResponse({"ok": True}, status=202)

            txn.callback_received = True
            txn.signature_valid = True
            txn.raw_event = event
            txn.save(
                update_fields=["callback_received", "signature_valid", "raw_event", "updated_at"]
            )

            if event_type in ("payment_intent.succeeded", "checkout.session.completed"):
                txn = process_success(txn=txn, gateway_reference=payment_intent, request_id=request_id)
                apply_org_settlement(txn, provider="stripe", raw_body=request.body, payload=event)
                to_email = getattr(getattr(txn, "user", None), "email", None)
                if to_email:
                    emit_once(
                        event_key=f"payment_success:{txn.reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_payment_email(
                            to_email, txn.order_id, txn.amount, txn.reference, "received"
                        ),
                    )
                if (
                    getattr(txn, "status", None) == TxnStatus.REFUNDED
                    and to_email
                    and getattr(txn, "refund_reference", None)
                ):
                    emit_once(
                        event_key=f"refund_completed:{txn.refund_reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_refund_email(
                            to_email, txn.order_id, txn.amount, txn.refund_reference, "completed"
                        ),
                    )
            elif event_type in ("payment_intent.payment_failed", "checkout.session.expired"):
                txn = process_failure(txn=txn, request_id=request_id)
                to_email = getattr(getattr(txn, "user", None), "email", None)
                if to_email:
                    emit_once(
                        event_key=f"payment_failed:{txn.reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_payment_email(
                            to_email, txn.order_id, txn.amount, txn.reference, "failed"
                        ),
                    )
            else:
                # Unhandled event; acknowledge to stop retries
                return JsonResponse({"ok": True}, status=200)

        return JsonResponse({"ok": True})


# ---------------------------
# Paystack Webhook
# ---------------------------
@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        request_id = hashlib.sha256(request.body).hexdigest()[:16]

        # 1) Verify signature & parse
        try:
            data = verify_paystack(request)
        except ValidationError as e:
            msg = (str(e) or "").lower()
            if "json" in msg:
                return JsonResponse({"detail": "invalid json"}, status=400)
            AuditLog.log(
                event="WEBHOOK_SIGNATURE_INVALID",
                request_id=request_id,
                message="invalid signature",
            )
            return JsonResponse({"detail": "invalid signature"}, status=401)

        # 2) Idempotency (provider retries)
        if not accept_once(scope="webhook:paystack", request=request):
            return HttpResponse(status=200)

        ref = (data.get("data") or {}).get("reference")
        if not ref:
            AuditLog.log(event="WEBHOOK_MISSING_REFERENCE", request_id=request_id)
            return JsonResponse({"ok": True}, status=202)

        with dbtx.atomic():
            try:
                txn = Transaction.objects.select_for_update().get(reference=ref)
            except Transaction.DoesNotExist:
                AuditLog.log(
                    event="WEBHOOK_UNKNOWN_REFERENCE",
                    request_id=request_id,
                    meta={"reference": ref},
                )
                return JsonResponse({"ok": True}, status=202)

            txn.callback_received = True
            txn.signature_valid = True  # verify_paystack passed => valid
            txn.raw_event = data
            txn.save(
                update_fields=["callback_received", "signature_valid", "raw_event", "updated_at"]
            )

            status_ = (data.get("data") or {}).get("status")
            gateway_ref = (data.get("data") or {}).get("id") or ref

            if status_ == "success":
                txn = process_success(txn=txn, gateway_reference=gateway_ref, request_id=request_id)
                apply_org_settlement(txn, provider="paystack", raw_body=request.body, payload=data)
                to_email = getattr(getattr(txn, "user", None), "email", None)
                if to_email:
                    emit_once(
                        event_key=f"payment_success:{txn.reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_payment_email(
                            to_email, txn.order_id, txn.amount, txn.reference, "received"
                        ),
                    )
                if (
                    getattr(txn, "status", None) == TxnStatus.REFUNDED
                    and to_email
                    and getattr(txn, "refund_reference", None)
                ):
                    emit_once(
                        event_key=f"refund_completed:{txn.refund_reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_refund_email(
                            to_email, txn.order_id, txn.amount, txn.refund_reference, "completed"
                        ),
                    )
            else:
                txn = process_failure(txn=txn, request_id=request_id)
                to_email = getattr(getattr(txn, "user", None), "email", None)
                if to_email:
                    emit_once(
                        event_key=f"payment_failed:{txn.reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_payment_email(
                            to_email, txn.order_id, txn.amount, txn.reference, "failed"
                        ),
                    )

        return JsonResponse({"ok": True})


# ---------------------------
# M-Pesa (Daraja) Webhook
# ---------------------------
@method_decorator(csrf_exempt, name="dispatch")
class MPesaWebhookView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        request_id = hashlib.sha256(request.body).hexdigest()[:16]

        try:
            data = verify_mpesa(request)
        except ValidationError as e:
            AuditLog.log(event="WEBHOOK_SIGNATURE_INVALID", request_id=request_id, message=str(e))
            return JsonResponse({"ok": False}, status=400)

        # 1) Idempotency (provider retries)
        if not accept_once(scope="webhook:mpesa", request=request):
            return HttpResponse(status=200)

        # 2) Parse standard STK callback
        callback = (data.get("Body") or {}).get("stkCallback", {}) or {}
        items = (callback.get("CallbackMetadata") or {}).get("Item", []) or []
        meta = {i.get("Name"): i.get("Value") for i in items}

        ref = callback.get("Reference") or callback.get("MerchantRequestID")
        if not ref:
            AuditLog.log(event="WEBHOOK_MISSING_REFERENCE", request_id=request_id)
            return JsonResponse({"ok": True}, status=202)

        with dbtx.atomic():
            try:
                txn = Transaction.objects.select_for_update().get(reference=ref)
            except Transaction.DoesNotExist:
                AuditLog.log(
                    event="WEBHOOK_UNKNOWN_REFERENCE",
                    request_id=request_id,
                    meta={"reference": ref},
                )
                return JsonResponse({"ok": True}, status=202)

            txn.callback_received = True
            txn.signature_valid = True  # verify_mpesa passed
            txn.raw_event = data
            txn.save(
                update_fields=["callback_received", "signature_valid", "raw_event", "updated_at"]
            )

            result_code = callback.get("ResultCode")
            gateway_ref = meta.get("MpesaReceiptNumber")

            if result_code == 0:
                txn = process_success(txn=txn, gateway_reference=gateway_ref, request_id=request_id)
                apply_org_settlement(txn, provider="mpesa", raw_body=request.body, payload=data)
                to_email = getattr(getattr(txn, "user", None), "email", None)
                if to_email:
                    emit_once(
                        event_key=f"payment_success:{txn.reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_payment_email(
                            to_email, txn.order_id, txn.amount, txn.reference, "received"
                        ),
                    )
                if (
                    getattr(txn, "status", None) == TxnStatus.REFUNDED
                    and to_email
                    and getattr(txn, "refund_reference", None)
                ):
                    emit_once(
                        event_key=f"refund_completed:{txn.refund_reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_refund_email(
                            to_email, txn.order_id, txn.amount, txn.refund_reference, "completed"
                        ),
                    )
            else:
                txn = process_failure(txn=txn, request_id=request_id)
                to_email = getattr(getattr(txn, "user", None), "email", None)
                if to_email:
                    emit_once(
                        event_key=f"payment_failed:{txn.reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_payment_email(
                            to_email, txn.order_id, txn.amount, txn.reference, "failed"
                        ),
                    )

        return JsonResponse({"ok": True})

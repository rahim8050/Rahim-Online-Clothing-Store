from decimal import Decimal
import json
import uuid
import hashlib

from django.db import transaction as dbtx
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from .models import Transaction, AuditLog
from orders.models import PaymentEvent
from .services import (
    init_checkout,
    verify_stripe,
    verify_paystack,
    verify_mpesa,
    process_success,
    process_failure,
)
from .enums import TxnStatus
from payments.notify import emit_once, send_payment_email, send_refund_email


# ---------------------------
# Checkout (requires session)
# ---------------------------
@method_decorator(csrf_exempt, name="dispatch")   # API-style; you already auth via session
@method_decorator(login_required, name="dispatch")
class CheckoutView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

        required = ["order_id", "amount", "currency", "gateway", "method", "idempotency_key"]
        missing = [k for k in required if k not in data]
        if missing:
            return JsonResponse({"ok": False, "error": f"missing_{missing[0]}"}, status=400)

        from orders.models import Order
        order = get_object_or_404(Order, pk=data["order_id"], user=request.user)

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
        return JsonResponse({
            "ok": True,
            "reference": txn.reference,
            "gateway": txn.gateway,
            "next_action": {},
        })


# ---------------------------
# Stripe Webhook
# ---------------------------
@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    def post(self, request, *args, **kwargs):
        request_id = getattr(request, "request_id", "")
        try:
            event = verify_stripe(request)   # validate signature, parse JSON
            sig_valid = True
        except Exception as e:
            AuditLog.log(event="WEBHOOK_SIGNATURE_INVALID", request_id=request_id, message=str(e))
            return JsonResponse({"ok": False}, status=400)

        obj = event.get("data", {}).get("object", {}) or {}
        reference = (obj.get("metadata") or {}).get("reference")
        if not reference:
            AuditLog.log(event="WEBHOOK_MISSING_REFERENCE", request_id=request_id)
            return JsonResponse({"ok": True}, status=202)

        event_type = event.get("type")
        gateway_ref = obj.get("payment_intent") or obj.get("id")

        with dbtx.atomic():
            try:
                txn = Transaction.objects.select_for_update().get(reference=reference)
            except Transaction.DoesNotExist:
                AuditLog.log(event="WEBHOOK_UNKNOWN_REFERENCE", request_id=request_id, meta={"reference": reference})
                return JsonResponse({"ok": True}, status=202)

            txn.callback_received = True
            txn.signature_valid = sig_valid
            txn.raw_event = event
            txn.save(update_fields=["callback_received", "signature_valid", "raw_event", "updated_at"])

            if event_type in ("payment_intent.succeeded", "checkout.session.completed"):
                txn = process_success(txn=txn, gateway_reference=gateway_ref, request_id=request_id)
                outcome = "received"
                notif_key = f"payment_success:{txn.reference}"
            elif event_type in ("payment_intent.payment_failed", "checkout.session.expired"):
                txn = process_failure(txn=txn, request_id=request_id)
                outcome = "failed"
                notif_key = f"payment_failed:{txn.reference}"
            else:
                # Unhandled event; acknowledge to avoid retries
                return JsonResponse({"ok": True}, status=200)

        # Post-commit notifications (idempotent)
        to_email = getattr(getattr(txn, "user", None), "email", None)
        if to_email:
            if outcome == "received":
                emit_once(
                    event_key=notif_key,
                    user=getattr(txn, "user", None),
                    channel="email",
                    payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                    send_fn=lambda: send_payment_email(to_email, txn.order_id, txn.amount, txn.reference, "received"),
                )
                if txn.status == TxnStatus.REFUNDED and getattr(txn, "refund_reference", None):
                    emit_once(
                        event_key=f"refund_completed:{txn.refund_reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_refund_email(to_email, txn.order_id, txn.amount, txn.refund_reference, "completed"),
                    )
            elif outcome == "failed":
                emit_once(
                    event_key=notif_key,
                    user=getattr(txn, "user", None),
                    channel="email",
                    payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                    send_fn=lambda: send_payment_email(to_email, txn.order_id, txn.amount, txn.reference, "failed"),
                )

        return JsonResponse({"ok": True})


# ---------------------------
# Paystack Webhook
# ---------------------------
@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(View):
    def post(self, request, *args, **kwargs):
        request_id = getattr(request, "request_id", "")
        try:
            data = verify_paystack(request)  # validates signature + parses JSON
            sig_valid = True
        except ValidationError as e:
            msg = (str(e) or "").lower()
            if "json" in msg:
                return JsonResponse({"detail": "invalid json"}, status=400)
            AuditLog.log(event="WEBHOOK_SIGNATURE_INVALID", request_id=request_id, message="invalid signature")
            return JsonResponse({"detail": "invalid signature"}, status=401)
        except Exception as e:
            AuditLog.log(event="WEBHOOK_SIGNATURE_INVALID", request_id=request_id, message=str(e))
            return JsonResponse({"ok": False}, status=400)

        raw = request.body or b""
        body_sha256 = hashlib.sha256(raw).hexdigest().lower()
        ref = data.get("data", {}).get("reference")
        if not ref:
            AuditLog.log(event="WEBHOOK_MISSING_REFERENCE", request_id=request_id)
            return JsonResponse({"detail": "missing reference"}, status=400)

        # Idempotency on raw body
        pe, created = PaymentEvent.objects.get_or_create(
            body_sha256=body_sha256,
            defaults={"provider": "paystack", "reference": ref, "body": data},
        )
        if not created:
            return HttpResponse(status=200)

        status_ = data.get("data", {}).get("status")
        gateway_ref = data.get("data", {}).get("id") or ref

        with dbtx.atomic():
            try:
                txn = Transaction.objects.select_for_update().get(reference=ref)
            except Transaction.DoesNotExist:
                AuditLog.log(event="WEBHOOK_UNKNOWN_REFERENCE", request_id=request_id, meta={"reference": ref})
                return JsonResponse({"ok": True}, status=202)

            txn.callback_received = True
            txn.signature_valid = sig_valid
            txn.raw_event = data
            txn.save(update_fields=["callback_received", "signature_valid", "raw_event", "updated_at"])

            if status_ == "success":
                txn = process_success(txn=txn, gateway_reference=gateway_ref, request_id=request_id)
                outcome = "received"
                notif_key = f"payment_success:{txn.reference}"
            else:
                txn = process_failure(txn=txn, request_id=request_id)
                outcome = "failed"
                notif_key = f"payment_failed:{txn.reference}"

        to_email = getattr(getattr(txn, "user", None), "email", None)
        if to_email:
            if outcome == "received":
                emit_once(
                    event_key=notif_key,
                    user=getattr(txn, "user", None),
                    channel="email",
                    payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                    send_fn=lambda: send_payment_email(to_email, txn.order_id, txn.amount, txn.reference, "received"),
                )
                if txn.status == TxnStatus.REFUNDED and getattr(txn, "refund_reference", None):
                    emit_once(
                        event_key=f"refund_completed:{txn.refund_reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_refund_email(to_email, txn.order_id, txn.amount, txn.refund_reference, "completed"),
                    )
            else:
                emit_once(
                    event_key=notif_key,
                    user=getattr(txn, "user", None),
                    channel="email",
                    payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                    send_fn=lambda: send_payment_email(to_email, txn.order_id, txn.amount, txn.reference, "failed"),
                )

        return JsonResponse({"ok": True})


# ---------------------------
# M-Pesa Webhook
# ---------------------------
@method_decorator(csrf_exempt, name="dispatch")
class MPesaWebhookView(View):
    def post(self, request, *args, **kwargs):
        request_id = getattr(request, "request_id", "")
        try:
            data = verify_mpesa(request)  # validates signature + parses JSON
        except Exception as e:
            AuditLog.log(event="WEBHOOK_SIGNATURE_INVALID", request_id=request_id, message=str(e))
            return JsonResponse({"ok": False}, status=400)

        callback = (data.get("Body") or {}).get("stkCallback", {}) or {}
        items = (callback.get("CallbackMetadata") or {}).get("Item", []) or []
        meta = {i.get("Name"): i.get("Value") for i in items if isinstance(i, dict)}
        ref = callback.get("Reference") or callback.get("MerchantRequestID")
        if not ref:
            AuditLog.log(event="WEBHOOK_MISSING_REFERENCE", request_id=request_id)
            return JsonResponse({"ok": True}, status=202)

        result_code = callback.get("ResultCode")
        gateway_ref = meta.get("MpesaReceiptNumber")

        with dbtx.atomic():
            try:
                txn = Transaction.objects.select_for_update().get(reference=ref)
            except Transaction.DoesNotExist:
                AuditLog.log(event="WEBHOOK_UNKNOWN_REFERENCE", request_id=request_id, meta={"reference": ref})
                return JsonResponse({"ok": True}, status=202)

            txn.callback_received = True
            txn.signature_valid = True
            txn.raw_event = data
            txn.save(update_fields=["callback_received", "signature_valid", "raw_event", "updated_at"])

            if result_code == 0:
                txn = process_success(txn=txn, gateway_reference=gateway_ref, request_id=request_id)
                outcome = "received"
                notif_key = f"payment_success:{txn.reference}"
            else:
                txn = process_failure(txn=txn, request_id=request_id)
                outcome = "failed"
                notif_key = f"payment_failed:{txn.reference}"

        to_email = getattr(getattr(txn, "user", None), "email", None)
        if to_email:
            if outcome == "received":
                emit_once(
                    event_key=notif_key,
                    user=getattr(txn, "user", None),
                    channel="email",
                    payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                    send_fn=lambda: send_payment_email(to_email, txn.order_id, txn.amount, txn.reference, "received"),
                )
                if txn.status == TxnStatus.REFUNDED and getattr(txn, "refund_reference", None):
                    emit_once(
                        event_key=f"refund_completed:{txn.refund_reference}",
                        user=getattr(txn, "user", None),
                        channel="email",
                        payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                        send_fn=lambda: send_refund_email(to_email, txn.order_id, txn.amount, txn.refund_reference, "completed"),
                    )
            else:
                emit_once(
                    event_key=notif_key,
                    user=getattr(txn, "user", None),
                    channel="email",
                    payload={"order_id": txn.order_id, "amount": str(txn.amount)},
                    send_fn=lambda: send_payment_email(to_email, txn.order_id, txn.amount, txn.reference, "failed"),
                )

        return JsonResponse({"ok": True})

from decimal import Decimal
import json
import uuid
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


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(login_required, name="dispatch")
class CheckoutView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body.decode())
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)
        required = [
            "order_id",
            "amount",
            "currency",
            "gateway",
            "method",
            "idempotency_key",
        ]
        for key in required:
            if key not in data:
                return JsonResponse({"ok": False, "error": f"missing_{key}"}, status=400)
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
        return JsonResponse(
            {
                "ok": True,
                "reference": txn.reference,
                "gateway": txn.gateway,
                "next_action": {},
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    def post(self, request, *args, **kwargs):
        request_id = getattr(request, "request_id", "")
        try:
            event = verify_stripe(request)
            sig_valid = True
        except Exception as e:
            AuditLog.log(event="WEBHOOK_SIGNATURE_INVALID", request_id=request_id, message=str(e))
            return JsonResponse({"ok": False}, status=400)
        obj = event.get("data", {}).get("object", {})
        reference = obj.get("metadata", {}).get("reference")
        if not reference:
            AuditLog.log(event="WEBHOOK_MISSING_REFERENCE", request_id=request_id)
            return JsonResponse({"ok": True}, status=202)
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
            payment_intent = obj.get("payment_intent") or obj.get("id")
            event_type = event.get("type")
            if event_type in ("payment_intent.succeeded", "checkout.session.completed"):
                process_success(txn=txn, gateway_reference=payment_intent, request_id=request_id)
            elif event_type in ("payment_intent.payment_failed", "checkout.session.expired"):
                process_failure(txn=txn, request_id=request_id)
        return JsonResponse({"ok": True})


@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(View):
    def post(self, request, *args, **kwargs):
        request_id = getattr(request, "request_id", "")
        try:
            data = verify_paystack(request)
            sig_valid = True
        except ValidationError as e:
            # Differentiate signature vs JSON issues without leaking secrets
            msg = (str(e) or "").lower()
            if "json" in msg:
                return JsonResponse({"detail": "invalid json"}, status=400)
            AuditLog.log(event="WEBHOOK_SIGNATURE_INVALID", request_id=request_id, message="invalid signature")
            return JsonResponse({"detail": "invalid signature"}, status=401)
        # Idempotency via body hash of raw request
        import hashlib
        raw = request.body
        body_sha256 = hashlib.sha256(raw).hexdigest().lower()
        ref = data.get("data", {}).get("reference")
        if not ref:
            AuditLog.log(event="WEBHOOK_MISSING_REFERENCE", request_id=request_id)
            return JsonResponse({"detail": "missing reference"}, status=400)
        # Upsert PaymentEvent for idempotency; duplicate bodies are acknowledged with 200
        pe, created = PaymentEvent.objects.get_or_create(
            body_sha256=body_sha256,
            defaults={"provider": "paystack", "reference": ref, "body": data},
        )
        if not created:
            return HttpResponse(status=200)
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
            status_ = data.get("data", {}).get("status")
            gateway_ref = data.get("data", {}).get("id") or ref
            if status_ == "success":
                process_success(txn=txn, gateway_reference=gateway_ref, request_id=request_id)
            else:
                process_failure(txn=txn, request_id=request_id)
        return JsonResponse({"ok": True})


@method_decorator(csrf_exempt, name="dispatch")
class MPesaWebhookView(View):
    def post(self, request, *args, **kwargs):
        request_id = getattr(request, "request_id", "")
        try:
            data = verify_mpesa(request)
        except Exception as e:
            AuditLog.log(event="WEBHOOK_SIGNATURE_INVALID", request_id=request_id, message=str(e))
            return JsonResponse({"ok": False}, status=400)
        callback = data.get("Body", {}).get("stkCallback", {})
        items = callback.get("CallbackMetadata", {}).get("Item", [])
        meta = {i.get("Name"): i.get("Value") for i in items}
        ref = callback.get("Reference") or callback.get("MerchantRequestID")
        if not ref:
            AuditLog.log(event="WEBHOOK_MISSING_REFERENCE", request_id=request_id)
            return JsonResponse({"ok": True}, status=202)
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
            result_code = callback.get("ResultCode")
            gateway_ref = meta.get("MpesaReceiptNumber")
            if result_code == 0:
                process_success(txn=txn, gateway_reference=gateway_ref, request_id=request_id)
            else:
                process_failure(txn=txn, request_id=request_id)
        return JsonResponse({"ok": True})

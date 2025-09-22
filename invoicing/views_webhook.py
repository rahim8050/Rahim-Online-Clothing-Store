from __future__ import annotations

import hashlib
import hmac
import json

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from payments.idempotency import accept_once
from .models import Invoice


@method_decorator(csrf_exempt, name="dispatch")
class EtimsWebhookView(View):
    def post(self, request, *args, **kwargs):
        # Verify HMAC (X-ETIMS-Signature) over raw body using ETIMS_WEBHOOK_SECRET
        secret = (getattr(settings, "ETIMS_WEBHOOK_SECRET", None) or "sandbox").encode("utf-8")
        raw = request.body or b""
        sig = (request.META.get("HTTP_X_ETIMS_SIGNATURE", "") or "").strip().lower()
        expected = hmac.new(secret, raw, hashlib.sha256).hexdigest()
        if not sig or not hmac.compare_digest(expected, sig):
            return JsonResponse({"detail": "invalid signature"}, status=401)

        # Idempotency: accept the first delivery of this exact payload only
        if not accept_once(scope="webhook:etims", request=request):
            return JsonResponse({"ok": True})

        # Parse JSON
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return JsonResponse({"detail": "invalid json"}, status=400)

        inv_id = data.get("invoice_id")
        if not inv_id:
            return JsonResponse({"detail": "missing invoice_id"}, status=400)

        status_ = (data.get("status") or "").lower()
        irn = (data.get("irn") or "").strip()
        message = (data.get("message") or "").strip()

        try:
            inv = Invoice.objects.get(pk=inv_id)
        except Invoice.DoesNotExist:
            # Unknown invoice: ack so provider stops retrying
            return JsonResponse({"ok": True}, status=202)

        # Apply status idempotently; never downgrade ACCEPTED to REJECTED
        if status_ == "accepted":
            updates = ["status", "updated_at"]
            if not inv.irn and irn:
                inv.irn = irn
                updates.append("irn")
            if inv.last_error:
                inv.last_error = ""
                updates.append("last_error")
            if inv.accepted_at is None:
                inv.accepted_at = timezone.now()
                updates.append("accepted_at")
            inv.status = Invoice.Status.ACCEPTED
            inv.save(update_fields=updates)

        elif status_ == "rejected":
            if inv.status != Invoice.Status.ACCEPTED:
                updates = ["status", "updated_at", "last_error"]
                inv.status = Invoice.Status.REJECTED
                inv.last_error = message
                if inv.rejected_at is None:
                    inv.rejected_at = timezone.now()
                    updates.append("rejected_at")
                inv.save(update_fields=updates)

        # Unknown statuses are ignored but acknowledged
        return JsonResponse({"ok": True})

from __future__ import annotations

import hashlib
import hmac
import json

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from payments.idempotency import accept_once

from .models import Invoice


@method_decorator(csrf_exempt, name="dispatch")
class EtimsWebhookView(View):
    def post(self, request, *args, **kwargs):
        secret = getattr(settings, "ETIMS_WEBHOOK_SECRET", None) or "sandbox"
        raw = request.body
        sig = (request.META.get("HTTP_X_ETIMS_SIGNATURE", "") or "").strip().lower()
        expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not sig or not hmac.compare_digest(expected, sig):
            return JsonResponse({"detail": "invalid signature"}, status=401)
        if not accept_once(scope="webhook:etims", request=request):
            return JsonResponse({"ok": True})
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return JsonResponse({"detail": "invalid json"}, status=400)

        inv_id = data.get("invoice_id")
        status_ = (data.get("status") or "").lower()
        irn = data.get("irn") or ""
        message = data.get("message") or ""
        try:
            inv = Invoice.objects.get(pk=inv_id)
        except Invoice.DoesNotExist:
            return JsonResponse({"ok": True}, status=202)

        # Flip status idempotently
        if status_ == "accepted":
            inv.status = Invoice.Status.ACCEPTED
            inv.irn = inv.irn or irn
            inv.last_error = ""
            inv.save(update_fields=["status", "irn", "last_error", "updated_at"])
        elif status_ == "rejected":
            inv.status = Invoice.Status.REJECTED
            inv.last_error = message
            inv.irn = inv.irn if inv.irn else ""
            inv.save(update_fields=["status", "last_error", "updated_at", "irn"])
        else:
            # ignore unknown
            pass
        return JsonResponse({"ok": True})

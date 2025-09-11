from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from payments.idempotency import idempotent
from invoicing.models import Invoice


@dataclass
class EtimsResult:
    status: str
    irn: str | None = None
    errors: Dict[str, Any] | None = None


class EtimsClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = base_url or getattr(settings, "ETIMS_BASE_URL", "https://sandbox.etims.local")
        self.api_key = api_key or getattr(settings, "ETIMS_API_KEY", None)

    def submit_invoice(self, invoice: Invoice) -> EtimsResult:  # pragma: no cover - abstract
        raise NotImplementedError


class SandboxEtimsClient(EtimsClient):
    def submit_invoice(self, invoice: Invoice) -> EtimsResult:
        # Fake simple rule: if buyer_name contains 'REJECT' -> reject
        name = (invoice.buyer_name or "").upper()
        if "REJECT" in name:
            return EtimsResult(status="rejected", errors={"message": "Sandbox rejection"})
        irn = f"IRN-{uuid.uuid4().hex[:12].upper()}"
        return EtimsResult(status="accepted", irn=irn)


def get_client() -> EtimsClient:
    # For now always sandbox; wire toggle via settings if needed later
    return SandboxEtimsClient()


@idempotent(scope="invoice:submit")
def submit_invoice(*, invoice: Invoice, idempotency_key: str | None = None) -> EtimsResult:
    """Submit an invoice to eTIMS (sandbox adapter). Idempotent per invoice.

    - If invoice is already ACCEPTED, return immediately.
    - Transition DRAFT/REJECTED -> SUBMITTED -> ACCEPTED/REJECTED
    - Persist IRN on acceptance; set timestamps accordingly
    """
    with transaction.atomic():
        invoice.refresh_from_db()
        if invoice.status == Invoice.Status.ACCEPTED:
            return EtimsResult(status="accepted", irn=invoice.irn or None)

        # Move to SUBMITTED if still draft/rejected
        if invoice.status in {Invoice.Status.DRAFT, Invoice.Status.REJECTED, Invoice.Status.SUBMITTED}:
            invoice.status = Invoice.Status.SUBMITTED
            invoice.submitted_at = invoice.submitted_at or timezone.now()
            invoice.save(update_fields=["status", "submitted_at", "updated_at"])

        client = get_client()
        result = client.submit_invoice(invoice)

        if result.status == "accepted":
            invoice.status = Invoice.Status.ACCEPTED
            invoice.irn = result.irn or invoice.irn or ""
            invoice.accepted_at = timezone.now()
            invoice.last_error = ""
            invoice.save(update_fields=["status", "irn", "accepted_at", "last_error", "updated_at"])
        else:
            invoice.status = Invoice.Status.REJECTED
            invoice.rejected_at = timezone.now()
            # capture error message
            msg = ""
            try:
                msg = (result.errors or {}).get("message") or ""
            except Exception:
                msg = ""
            invoice.last_error = msg
            invoice.save(update_fields=["status", "rejected_at", "last_error", "updated_at"])

        return result


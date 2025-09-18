from __future__ import annotations

from typing import Optional

from django.db.models import QuerySet

from .models import Invoice


def get_invoice_for_order(order_id: int) -> Optional[Invoice]:
    return Invoice.objects.filter(order_id=order_id).first()


def list_org_invoices(org_id: int, **filters) -> QuerySet[Invoice]:
    qs = Invoice.objects.filter(org_id=org_id)
    status = filters.get("status")
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-issued_at")


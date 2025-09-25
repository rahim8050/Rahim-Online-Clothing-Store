from __future__ import annotations

from django.core.exceptions import FieldError
from django.db.models import QuerySet

from .kpi import get_realtime_kpi_snapshot
from .models import VendorOrg


def org_scoped_queryset(
    qs: QuerySet, *, org: VendorOrg | None = None, org_id: int | None = None
) -> QuerySet:
    """Restrict a queryset to a specific org.

    Attempts model.org filtering first, then falls back to owner->vendor_profile->org.
    """
    if org is None and org_id is None:
        raise ValueError("Provide org or org_id")
    if org is None:
        org = VendorOrg.objects.get(pk=org_id)

    try:
        return qs.filter(org=org)
    except FieldError:
        # Fallback to owner -> vendor_profile -> org
        return qs.filter(owner__vendor_profile__org=org)


def get_kpis(org_id: int, window: str, last_n: int = 30):
    from .models import VendorKPI

    qs = VendorKPI.objects.filter(org_id=org_id, window=window).order_by(
        "-period_start"
    )
    return qs[:last_n]


def get_realtime(org_id: int):
    return get_realtime_kpi_snapshot(org_id)

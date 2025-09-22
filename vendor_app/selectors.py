from __future__ import annotations

from typing import Optional

from django.core.exceptions import FieldError
from django.db.models import QuerySet

from .kpi import get_realtime_kpi_snapshot
from .models import VendorKPI, VendorOrg


def org_scoped_queryset(
    qs: QuerySet, *, org: VendorOrg | None = None, org_id: int | None = None
) -> QuerySet:
    """
    Restrict a queryset to a specific org.

    Tries `model.org` first; if the model has no `org` FK, falls back to
    `owner -> vendor_profile -> org`.
    """
    if org is None and org_id is None:
        raise ValueError("Provide org or org_id")
    if org is None:
        org = VendorOrg.objects.get(pk=org_id)

    try:
        return qs.filter(org=org)
    except FieldError:
        # Fallback: models that relate to an owner user, which maps to an org via VendorProfile
        return qs.filter(owner__vendor_profile__org=org)


def get_kpis(org_id: int, window: str, last_n: int = 30) -> QuerySet[VendorKPI]:
    qs = VendorKPI.objects.filter(org_id=org_id, window=window).order_by("-period_start")
    return qs[:last_n]


def get_realtime(org_id: int) -> dict:
    return get_realtime_kpi_snapshot(org_id)

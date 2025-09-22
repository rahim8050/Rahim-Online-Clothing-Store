from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import PermissionDenied

from .models import VendorMember, VendorOrg

# Role ranking for minimum checks
ROLE_RANK = {"STAFF": 1, "MANAGER": 2, "OWNER": 3}


def rank(role: str) -> int:
    return ROLE_RANK.get((role or "").upper(), 0)


def get_active_membership(user, org: VendorOrg) -> VendorMember | None:
    try:
        return VendorMember.objects.select_related("org", "user").get(
            org=org, user=user, is_active=True
        )
    except VendorMember.DoesNotExist:
        return None


def is_in_org(user, org: VendorOrg) -> bool:
    return get_active_membership(user, org) is not None


def has_min_role(user, org: VendorOrg, min_role: str) -> bool:
    m = get_active_membership(user, org)
    return bool(m and rank(m.role) >= rank(min_role))


def require_in_org(user, org: VendorOrg) -> VendorMember:
    m = get_active_membership(user, org)
    if not m:
        raise PermissionDenied("You are not a member of this organization.")
    return m


def require_min_role(user, org: VendorOrg, min_role: str) -> VendorMember:
    m = require_in_org(user, org)
    if rank(m.role) < rank(min_role):
        raise PermissionDenied("You do not have sufficient privileges for this action.")
    return m


def resolve_org_from_request(request, view=None) -> VendorOrg | None:
    """
    Best-effort resolver for an org from request/view.

    Tries, in order:
      - view.kwargs: org_id, org_pk, org, pk  (ints)  | org_slug, slug (str)
      - query params: org_id, org (ints) | org_slug (str)
      - body data:    org_id, org (ints) | org_slug (str)

    Returns None if not found or invalid.
    """
    org_id: int | None = None
    org_slug: str | None = None

    # From view kwargs
    if view is not None and hasattr(view, "kwargs"):
        for k in ("org_id", "org_pk", "org", "pk"):
            if k in view.kwargs:
                try:
                    org_id = int(view.kwargs[k])
                    break
                except Exception:
                    pass
        if org_id is None:
            for k in ("org_slug", "slug"):
                if k in view.kwargs:
                    org_slug = str(view.kwargs[k])
                    break

    # From query params
    if org_id is None and hasattr(request, "query_params"):
        for k in ("org_id", "org"):
            if k in request.query_params:
                try:
                    org_id = int(request.query_params.get(k))
                    break
                except Exception:
                    pass
        if org_id is None and "org_slug" in getattr(request, "query_params", {}):
            org_slug = request.query_params.get("org_slug")

    # From body
    if org_id is None and hasattr(request, "data"):
        for k in ("org_id", "org"):
            if k in request.data:
                try:
                    org_id = int(request.data.get(k))
                    break
                except Exception:
                    pass
        if org_id is None and "org_slug" in getattr(request, "data", {}):
            org_slug = request.data.get("org_slug")

    try:
        if org_id is not None:
            return VendorOrg.objects.get(pk=org_id)
        if org_slug:
            return VendorOrg.objects.get(slug=org_slug)
    except ObjectDoesNotExist:
        return None
    return None

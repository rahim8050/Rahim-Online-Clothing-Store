from __future__ import annotations

from typing import Optional

from django.http import HttpRequest
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from .models import VendorOrg
from .services import resolve_org_from_request, has_min_role


class _BaseOrgPermission(BasePermission):
    """Shared helpers for org-scoped permissions.

    Expects the view to carry an org identifier, typically via:
    - `view.kwargs['org_id']` or `view.kwargs['org_slug']`
    - or query/body parameter: `org_id` / `org_slug` / `org`
    """

    required_min_role: Optional[str] = None  # 'STAFF' | 'MANAGER' | 'OWNER' | None

    def has_permission(self, request: Request, view) -> bool:  # type: ignore[override]
        # Allow schema generation without requiring org context
        if getattr(view, "swagger_fake_view", False):
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False):
            return True
        org: Optional[VendorOrg] = resolve_org_from_request(request, view)
        if org is None:
            return False
        if self.required_min_role is None:
            # just membership
            return has_min_role(request.user, org, "STAFF")
        return has_min_role(request.user, org, self.required_min_role)

    def has_object_permission(self, request: Request, view, obj) -> bool:  # type: ignore[override]
        # Delegate to has_permission, assuming object is already org-filtered in queryset.
        return self.has_permission(request, view)


class IsInOrg(_BaseOrgPermission):
    """Member of the org (any role)."""

    required_min_role = None


class IsOrgStaff(_BaseOrgPermission):
    """STAFF or higher (includes MANAGER/OWNER)."""

    required_min_role = "STAFF"


class IsOrgManager(_BaseOrgPermission):
    """MANAGER or higher (includes OWNER)."""

    required_min_role = "MANAGER"


class IsOrgOwner(_BaseOrgPermission):
    """OWNER only (highest privilege)."""

    required_min_role = "OWNER"

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from .models import VendorOrg
from .services import has_min_role, resolve_org_from_request


class _BaseOrgPermission(BasePermission):
    """
    Shared helpers for org-scoped permissions.

    Expects the view to carry an org identifier via:
      - view.kwargs['org_id'] or view.kwargs['org_slug']
      - or query/body param: org_id / org_slug / org
    """

    # 'STAFF' | 'MANAGER' | 'OWNER' | None (None => any member)
    required_min_role: str | None = None

    def has_permission(self, request: Request, view) -> bool:  # type: ignore[override]
        # Allow schema generation without org context
        if getattr(view, "swagger_fake_view", False):
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        # Global admins bypass org checks
        if getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False):
            return True

        org: VendorOrg | None = resolve_org_from_request(request, view)
        if org is None:
            return False

        # If no specific role required, require membership (>= STAFF)
        min_role = self.required_min_role or "STAFF"
        return has_min_role(request.user, org, min_role)

    def has_object_permission(self, request: Request, view, obj) -> bool:  # type: ignore[override]
        # Assume queryset already filtered by org; reuse same check.
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

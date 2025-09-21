# core/permissions.py
from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission

from users.constants import DRIVER, VENDOR, VENDOR_STAFF
from users.utils import in_groups as _in_groups


# -------- helpers --------
def _token_to_scopes(auth: Any) -> set[str]:
    """
    Normalize various auth representations into a set of scopes.
    Supports:
      - dict-like: {'scopes': [...]} or {'scope': 'a b c'}
      - SimpleJWT token: has .payload dict
      - any object exposing .get('...') or .payload.get('...')
    """
    if auth is None:
        return set()

    # dict-like
    if hasattr(auth, "get"):
        scopes = auth.get("scopes")
        if scopes is None:
            scope_str = auth.get("scope")
            if isinstance(scope_str, str):
                return set(scope_str.split())
            return set()
        if isinstance(scopes, (list, tuple, set)):
            return set(map(str, scopes))
        if isinstance(scopes, str):
            return set(scopes.split())
        return set()

    # objects with .payload (e.g., SimpleJWT token)
    payload = getattr(auth, "payload", None)
    if isinstance(payload, dict):
        scopes = payload.get("scopes")
        if isinstance(scopes, (list, tuple, set)):
            return set(map(str, scopes))
        scope_str = payload.get("scope")
        if isinstance(scope_str, str):
            return set(scope_str.split())

    return set()


# -------- group-based --------
class InGroups(BasePermission):
    """
    Allow if the user is authenticated and belongs to ANY of required_groups.
    """

    required_groups: tuple[str, ...] = ()

    def has_permission(self, request, view) -> bool:
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return False
        if not self.required_groups:
            return True
        # users.utils.in_groups(user, *groups) should handle group names
        return _in_groups(request.user, *self.required_groups)


class IsDriver(InGroups):
    required_groups = (DRIVER,)


class IsVendorOrVendorStaff(InGroups):  # <-- match name used in your views
    required_groups = (VENDOR, VENDOR_STAFF)


# Backward-compatible alias (if some modules still import the old name)
IsVendorOrStaff = IsVendorOrVendorStaff


# -------- scope-based --------
class HasScope(BasePermission):
    """
    Grants access if request.auth contains the required scope.
    Usage:
        CatalogRead = HasScope.require('catalog:read')
        permission_classes = [CatalogRead]
    """

    required_scope: str | None = None

    def has_permission(self, request, view) -> bool:
        scope = getattr(self, "required_scope", None)
        if not scope:
            return False
        scopes = _token_to_scopes(getattr(request, "auth", None))
        return scope in scopes

    @classmethod
    def require(cls, scope: str) -> type[HasScope]:
        name = f"HasScope_{scope.replace(':', '_')}"
        return type(name, (cls,), {"required_scope": scope})


class HasVendorScope(BasePermission):
    """
    Read the required vendor scope off the view:
        class SomeAPI(APIView):
            permission_classes = [IsAuthenticated, HasVendorScope]
            required_vendor_scope = "delivery"
    This checks for 'vendor:<required_vendor_scope>' in request.auth scopes.
    """

    def has_permission(self, request, view) -> bool:
        required = getattr(view, "required_vendor_scope", None)
        if not required:
            # No scope declared on the view: deny by default (safer).
            return False
        needed = f"vendor:{required}"
        scopes = _token_to_scopes(getattr(request, "auth", None))
        return needed in scopes

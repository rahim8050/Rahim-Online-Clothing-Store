# users/permissions.py
from __future__ import annotations
from typing import TYPE_CHECKING

try:
    # Try normal DRF import first
    from rest_framework.permissions import BasePermission
except ImportError:
    # Fallback stub for typing & non-DRF environments
    if TYPE_CHECKING:

        class BasePermission:  # type: ignore[no-redef]
            ...
    else:

        class BasePermission:  # runtime fallback
            """Fallback for BasePermission if DRF is not installed."""

            pass


class IsVendorOrVendorStaff(BasePermission):
    message = "Vendor or active vendor staff role required."

    def has_permission(self, request, view) -> bool:
        u = getattr(request, "user", None)
        if not u or not getattr(u, "is_authenticated", False):
            return False

        # Admin/superuser always allowed
        if getattr(u, "is_superuser", False) or u.groups.filter(name="Admin").exists():
            return True

        in_vendor_group = u.groups.filter(name="Vendor").exists()
        try:
            from users.models import VendorStaff  # adjust app label

            is_active_staff = VendorStaff.objects.filter(
                staff=u, is_active=True
            ).exists()
        except Exception:
            is_active_staff = False

        return in_vendor_group or is_active_staff


class IsVendorOwner(BasePermission):
    """Owner-only operations (admin bypass allowed)."""

    message = "Only vendor owners can perform this action."

    def has_permission(self, request, view) -> bool:
        u = getattr(request, "user", None)
        if not u or not getattr(u, "is_authenticated", False):
            return False
        if getattr(u, "is_superuser", False) or u.groups.filter(name="Admin").exists():
            return True
        return u.groups.filter(name="Vendor").exists()


class HasVendorScope(BasePermission):
    """
    Owner passes automatically. For staff, require an active VendorStaff membership
    for the resolved owner context that includes the required scope in its JSON 'scopes'.

    Views can set attribute `required_vendor_scope` = 'catalog' | 'delivery' | ...
    """

    message = "Vendor scope required."

    def has_permission(self, request, view) -> bool:
        u = getattr(request, "user", None)
        if not u or not getattr(u, "is_authenticated", False):
            return False

        # Admin/superuser bypass
        if getattr(u, "is_superuser", False) or u.groups.filter(name="Admin").exists():
            return True

        # Owner bypass
        if u.groups.filter(name="Vendor").exists():
            return True

        # No scope required -> membership check handled by other permission
        scope = getattr(view, "required_vendor_scope", None)
        if not scope:
            return True

        # Resolve owner context if provided
        try:
            from users.utils import resolve_vendor_owner_for

            raw_owner = (
                request.data.get("owner_id")
                if request.method != "GET"
                else request.query_params.get("owner_id")
            )
            owner_id = resolve_vendor_owner_for(u, raw_owner)
        except Exception:
            return False

        try:
            from users.models import VendorStaff

            vs = VendorStaff.objects.filter(
                owner_id=owner_id, staff=u, is_active=True
            ).first()
            if not vs:
                return False
            scopes = vs.scopes or []
            return scope in scopes
        except Exception:
            return False


class NotBuyingOwnListing(BasePermission):
    """Deny when the requester is the product owner OR active vendor staff for that owner."""

    message = "You cannot purchase your own product."

    def _is_forbidden(self, user, product) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        owner_id = (
            getattr(product, "owner_id", None)
            or getattr(product, "vendor_id", None)
            or getattr(product, "user_id", None)
        )
        if owner_id is None:
            return False
        if owner_id == getattr(user, "id", None):
            return True
        try:
            from users.models import VendorStaff

            return VendorStaff.objects.filter(
                owner_id=owner_id, staff_id=user.id, is_active=True
            ).exists()
        except Exception:
            return False

    def has_object_permission(self, request, view, obj) -> bool:
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            self.message = "Authentication required."
            return False
        if self._is_forbidden(user, obj):
            if getattr(obj, "owner_id", None) == user.id:
                self.message = "You cannot purchase your own product."
            else:
                self.message = "You cannot purchase products for a vendor you work for."
            return False
        return True


class IsDriver(BasePermission):
    def has_permission(self, request, view) -> bool:
        u = getattr(request, "user", None)
        return bool(
            u
            and getattr(u, "is_authenticated", False)
            and u.groups.filter(name="Driver").exists()
        )

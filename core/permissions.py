from rest_framework.permissions import BasePermission
from users.constants import VENDOR, VENDOR_STAFF, DRIVER
from users.utils import in_groups


class InGroups(BasePermission):
    required_groups: tuple[str, ...] = ()

    def has_permission(self, request, view):
        return in_groups(request.user, *self.required_groups)


class IsDriver(InGroups):
    required_groups = (DRIVER,)


class IsVendorOrStaff(InGroups):
    required_groups = (VENDOR, VENDOR_STAFF)


class HasScope(BasePermission):
    """Permission that grants access if request.auth contains a required scope.

    Usage in views:
        CatalogRead = HasScope.require('catalog:read')
        permission_classes = [CatalogRead | IsAuthenticatedOrReadOnly]
    """

    required_scope: str | None = None

    def has_permission(self, request, view):
        scope = getattr(self, "required_scope", None)
        if not scope:
            return False
        auth = getattr(request, "auth", None)
        if not auth:
            return False
        try:
            scopes = set(auth.get("scopes", []) or [])
        except Exception:
            return False
        return scope in scopes

    @classmethod
    def require(cls, scope: str):
        # Return a subclass bound to the provided scope
        name = f"HasScope_{scope.replace(':', '_')}"
        return type(name, (cls,), {"required_scope": scope})

from rest_framework.permissions import BasePermission
from users.constants import VENDOR, VENDOR_STAFF, DRIVER
from users.utils import in_groups
from users.models import VendorStaff


class InGroups(BasePermission):
    required_groups: tuple[str, ...] = ()

    def has_permission(self, request, view):
        return in_groups(request.user, *self.required_groups)


class IsDriver(InGroups):
    required_groups = (DRIVER,)


class IsVendorOrStaff(InGroups):
    required_groups = (VENDOR, VENDOR_STAFF)


class NotBuyingOwnListing(BasePermission):
    message = "You cannot purchase your own or your vendor's listing."

    def _is_forbidden(self, user, product) -> bool:
        if not getattr(user, "is_authenticated", False):
            return False
        owner_id = getattr(product, "owner_id", None)
        if owner_id is None:
            return False
        if owner_id == user.id:
            return True
        return VendorStaff.objects.filter(
            owner_id=owner_id, staff_id=user.id, is_active=True
        ).exists()

    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        from product_app.models import Product
        from orders.models import OrderItem

        if isinstance(obj, Product):
            return not self._is_forbidden(request.user, obj)
        if isinstance(obj, OrderItem):
            return not self._is_forbidden(request.user, obj.product)
        return True

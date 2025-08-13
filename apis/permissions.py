from rest_framework.permissions import BasePermission
from users.models import VendorStaff


class NotBuyingOwnListing(BasePermission):
    """Block vendors or their staff from purchasing their own products."""

    message = "You cannot purchase your own listing."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user.is_authenticated:
            return False
        # obj might be a Product or have a product attribute
        product = getattr(obj, "product", obj)
        owner_id = getattr(product, "owner_id", None)
        if owner_id is None:
            return True
        if owner_id == user.id:
            return False
        if VendorStaff.objects.filter(owner_id=owner_id, staff=user, is_active=True).exists():
            return False
        return True

class InGroups(BasePermission):
    """Allow access only to users in specific Django groups."""
    def has_permission(self, request, view):
        required = getattr(view, "required_groups", [])
        return (
            request.user
            and request.user.is_authenticated
            and request.user.groups.filter(name__in=required).exists()
        )

# users/permissions.py (or your api app)
from rest_framework.permissions import BasePermission

class IsVendorOrVendorStaff(BasePermission):
    message = "Vendor or active vendor staff role required."

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False

        in_vendor_group = u.groups.filter(name="Vendor").exists()
        try:
            from users.models import VendorStaff  # adjust app label
            is_active_staff = VendorStaff.objects.filter(staff=u, is_active=True).exists()
        except Exception:
            is_active_staff = False

        return in_vendor_group or is_active_staff


try:
    # If DRF is installed, this lets you also reuse it on DRF views
    from rest_framework.permissions import BasePermission
except Exception:
    BasePermission = object  # fallback so it also works in plain Django views

class NotBuyingOwnListing(BasePermission):
    """
    Deny when the requester is the product owner OR active vendor staff for that owner.
    Works in both DRF and regular Django views:
      perm = NotBuyingOwnListing()
      if not perm.has_object_permission(request, None, product): ...
    """
    message = "You cannot purchase your own product."

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            self.message = "Authentication required."
            return False

        # Support different FK names just in case
        owner_id = (
            getattr(obj, "owner_id", None)
            or getattr(obj, "vendor_id", None)
            or getattr(obj, "user_id", None)
        )
        if owner_id is None:
            # If the model has no owner concept, allow by default
            return True

        if owner_id == user.id:
            self.message = "You cannot purchase your own product."
            return False

        # If you have VendorStaff, block purchases for vendors you work for
        try:
            from users.models import VendorStaff
            if VendorStaff.objects.filter(owner_id=owner_id, staff_id=user.id, is_active=True).exists():
                self.message = "You cannot purchase products for a vendor you work for."
                return False
        except Exception:
            # If model doesn't exist or query fails, just ignore staff check
            pass

        return True



class IsDriver(BasePermission):
    def has_permission(self, request, view):
        u = getattr(request, "user", None)
        return bool(u and u.is_authenticated and u.groups.filter(name="Driver").exists())

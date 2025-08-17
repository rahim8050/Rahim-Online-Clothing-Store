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
    """Deny when the requester is the product owner OR active vendor staff for that owner."""
    message = 'You cannot purchase your own product.'

    def _is_forbidden(self, user, product):
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        owner_id = (
            getattr(product, 'owner_id', None)
            or getattr(product, 'vendor_id', None)
            or getattr(product, 'user_id', None)
        )
        if owner_id is None:
            return False
        if owner_id == getattr(user, 'id', None):
            return True
        try:
            from users.models import VendorStaff
            return VendorStaff.objects.filter(owner_id=owner_id, staff_id=user.id, is_active=True).exists()
        except Exception:
            return False

    def has_object_permission(self, request, view, obj):
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            self.message = 'Authentication required.'
            return False
        if self._is_forbidden(user, obj):
            if getattr(obj, 'owner_id', None) == user.id:
                self.message = 'You cannot purchase your own product.'
            else:
                self.message = 'You cannot purchase products for a vendor you work for.'
            return False
        return True


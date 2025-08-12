from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import VendorStaff

User = get_user_model()

def vendor_owner_ids_for(user):
    """
    Return a queryset of User IDs that this user can act for as a vendor owner.
    Includes the user (if they are a Vendor) and any owners where they are active staff.
    """
    return User.objects.filter(
        Q(pk=user.pk, groups__name="Vendor") |
        Q(vendor_staff_owned__staff=user, vendor_staff_owned__is_active=True) |   # owner=User, staff=user (role owner row covers self)
        Q(vendor_staff_memberships__owner__groups__name="Vendor",
          vendor_staff_memberships__is_active=True)                                # staff of a vendor owner
    ).values_list("pk", flat=True).distinct()


def resolve_vendor_owner_for(user, owner_id=None):
    """
    Decide the vendor owner to use when creating a Product.
    - If user is Vendor -> default to self unless owner_id is given (and matches self).
    - If user is Vendor Staff -> require owner_id if they have multiple memberships; else pick the single owner.
    Raises ValueError if not resolvable/authorized.
    """
    ids = list(vendor_owner_ids_for(user))
    if not ids:
        raise ValueError("You are not a vendor or vendor staff.")

    if owner_id:
        if owner_id in ids:
            return owner_id
        raise ValueError("Not authorized to act for that vendor owner.")

    # No owner_id specified: pick the only one if unique, else force explicit choice
    if len(ids) == 1:
        return ids[0]
    raise ValueError("Multiple vendor owners found; specify owner_id.")

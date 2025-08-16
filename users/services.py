from django.contrib.auth.models import Group
from .constants import VENDOR_STAFF


def deactivate_vendor_staff(membership):
    membership.is_active = False
    membership.save(update_fields=["is_active"])

    user = membership.staff
    still_active = user.vendor_staff_memberships.filter(is_active=True).exists()
    if not still_active:
        try:
            g = Group.objects.get(name=VENDOR_STAFF)
            user.groups.remove(g)
        except Group.DoesNotExist:
            pass

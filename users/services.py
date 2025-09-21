# users/services.py
from django.contrib.auth.models import Group
from django.db import transaction

from users.constants import VENDOR_STAFF as GROUP_VENDOR_STAFF
from users.models import VendorStaff  # your model lives here


@transaction.atomic
def add_or_activate_staff(owner, staff, role="staff"):
    """
    Idempotent: exactly one row per (owner, staff).
    If it exists => activate + update role; else create active row.
    """
    row, created = VendorStaff.objects.select_for_update().get_or_create(
        owner=owner, staff=staff, defaults={"role": role, "is_active": True}
    )
    if not created:
        update_fields = []
        if not row.is_active:
            row.is_active = True
            update_fields.append("is_active")
        if role and getattr(row, "role", None) != role:
            row.role = role
            update_fields.append("role")
        if update_fields:
            row.save(update_fields=update_fields)
    # Ensure Django Group membership is in sync (idempotent)
    try:
        g, _ = Group.objects.get_or_create(name=GROUP_VENDOR_STAFF)
        g.user_set.add(staff)
    except Exception:
        pass

    return row


@transaction.atomic
def deactivate_staff(owner, staff):
    row = VendorStaff.objects.select_for_update().get(owner=owner, staff=staff)
    if row.is_active:
        row.is_active = False
        row.save(update_fields=["is_active"])
    # If no other active memberships remain for this staff, drop group
    try:
        still_active = VendorStaff.objects.filter(staff=staff, is_active=True).exists()
        if not still_active:
            g = Group.objects.get_or_create(name=GROUP_VENDOR_STAFF)[0]
            g.user_set.remove(staff)
    except Exception:
        pass
    return row


@transaction.atomic
def activate_vendor_staff(staff, owner_id):
    """Activate membership and add staff to the Vendor Staff group."""
    row, _ = VendorStaff.objects.select_for_update().get_or_create(
        owner_id=owner_id, staff=staff, defaults={"is_active": True}
    )
    if not row.is_active:
        row.is_active = True
        row.save(update_fields=["is_active"])
    try:
        g, _ = Group.objects.get_or_create(name=GROUP_VENDOR_STAFF)
        g.user_set.add(staff)
    except Exception:
        pass
    return row


@transaction.atomic
def deactivate_vendor_staff(staff_or_membership, owner_id=None):
    """
    Deactivate membership and remove group if last active membership.
    Accepts either (staff, owner_id) or a VendorStaff membership instance.
    """
    if owner_id is None:
        membership = staff_or_membership
        staff = membership.staff
        owner_id = membership.owner_id
    else:
        staff = staff_or_membership

    row = VendorStaff.objects.select_for_update().get(owner_id=owner_id, staff=staff)
    if row.is_active:
        row.is_active = False
        row.save(update_fields=["is_active"])
    try:
        if not VendorStaff.objects.filter(staff=staff, is_active=True).exists():
            g = Group.objects.get_or_create(name=GROUP_VENDOR_STAFF)[0]
            g.user_set.remove(staff)
    except Exception:
        pass
    return row

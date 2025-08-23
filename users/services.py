# users/services.py
from django.db import transaction
from users.models import VendorStaff  # your model lives here

@transaction.atomic
def add_or_activate_staff(owner, staff, role="staff"):
    """
    Idempotent: exactly one row per (owner, staff).
    If it exists => activate + update role; else create active row.
    """
    row, created = (
        VendorStaff.objects
        .select_for_update()
        .get_or_create(owner=owner, staff=staff, defaults={"role": role, "is_active": True})
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
    return row

@transaction.atomic
def deactivate_staff(owner, staff):
    row = (
        VendorStaff.objects
        .select_for_update()
        .get(owner=owner, staff=staff)
    )
    if row.is_active:
        row.is_active = False
        row.save(update_fields=["is_active"])
    return row

# Back-compat wrapper (some places import this name)
def deactivate_vendor_staff(membership):
    return deactivate_staff(membership.owner, membership.staff)

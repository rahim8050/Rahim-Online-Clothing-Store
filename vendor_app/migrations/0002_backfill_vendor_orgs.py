from __future__ import annotations

from django.db import migrations, transaction


def _chunked(iterable, size=500):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def backfill_vendor_orgs(apps, schema_editor):
    User = apps.get_model("users", "CustomUser")
    try:
        VendorStaff = apps.get_model("users", "VendorStaff")
    except LookupError:
        VendorStaff = None
    Product = apps.get_model("product_app", "Product")
    VendorOrg = apps.get_model("vendor_app", "VendorOrg")
    VendorMember = apps.get_model("vendor_app", "VendorMember")
    VendorProfile = apps.get_model("vendor_app", "VendorProfile")

    # Collect candidate legacy owners
    owner_ids = set()

    # 1) VendorStaff self-ownership rows (legacy owner marker)
    if VendorStaff is not None:
        for vs in VendorStaff.objects.all().only("owner_id", "staff_id", "role", "is_active"):
            try:
                if vs.is_active and vs.role == "owner" and vs.owner_id == vs.staff_id:
                    owner_ids.add(vs.owner_id)
            except Exception:
                continue

    # 2) Users who own at least one Product
    for row in Product.objects.exclude(owner_id=None).values_list("owner_id", flat=True).distinct():
        if row:
            owner_ids.add(int(row))

    created_orgs = 0
    created_owners = 0
    linked_profiles = 0

    # Process in chunks to avoid long transactions/locks
    for batch in _chunked(sorted(owner_ids)):
        with transaction.atomic():
            users = {u.id: u for u in User.objects.filter(id__in=batch)}
            for uid in batch:
                user = users.get(uid)
                if not user:
                    continue

                slug = f"vendor-{uid}"
                defaults = {
                    "name": (user.username or user.email or f"Vendor {uid}")[:120],
                    "owner_id": uid,
                }
                org, org_created = VendorOrg.objects.get_or_create(slug=slug, defaults=defaults)
                if org_created:
                    created_orgs += 1

                # Ensure OWNER membership (uppercase for new model)
                vm, vm_created = VendorMember.objects.get_or_create(
                    org_id=org.id, user_id=uid, defaults={"role": "OWNER", "is_active": True}
                )
                if not vm_created:
                    # Make sure role is OWNER and active
                    changed = False
                    if vm.role != "OWNER":
                        vm.role = "OWNER"
                        changed = True
                    if not vm.is_active:
                        vm.is_active = True
                        changed = True
                    if changed:
                        vm.save(update_fields=["role", "is_active", "updated_at"])
                else:
                    created_owners += 1

                # Link profile to org
                vp, _ = VendorProfile.objects.get_or_create(user_id=uid)
                if vp.org_id != org.id:
                    vp.org_id = org.id
                    vp.save(update_fields=["org", "updated_at"])
                    linked_profiles += 1

    print(
        f"vendor_app backfill: owners={len(owner_ids)}, created_orgs={created_orgs}, "
        f"owner_memberships_created={created_owners}, profiles_linked={linked_profiles}"
    )


def noop_reverse(apps, schema_editor):
    # Keep reversible without destructive deletes.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("vendor_app", "0001_initial"),
        ("product_app", "0010_backfill_product_version"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_vendor_orgs, noop_reverse),
    ]

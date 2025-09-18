from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models, transaction


def ensure_profiles_have_orgs(apps, schema_editor):
    VendorOrg = apps.get_model("vendor_app", "VendorOrg")
    VendorProfile = apps.get_model("vendor_app", "VendorProfile")
    User = apps.get_model("users", "CustomUser")

    qs = VendorProfile.objects.filter(org__isnull=True).values_list("id", "user_id")
    ids = list(qs)
    if not ids:
        return

    with transaction.atomic():
        users = {u.id: u for u in User.objects.filter(id__in=[u for _, u in ids])}
        for vpid, uid in ids:
            user = users.get(uid)
            if not user:
                # Skip orphaned profile rows (shouldn't happen in normal flow)
                continue
            slug = f"vendor-{uid}"
            org, _ = VendorOrg.objects.get_or_create(
                slug=slug,
                defaults={"name": (user.username or user.email or f"Vendor {uid}")[:120], "owner_id": uid},
            )
            VendorProfile.objects.filter(id=vpid).update(org_id=org.id)


class Migration(migrations.Migration):

    dependencies = [
        ("vendor_app", "0002_backfill_vendor_orgs"),
    ]

    operations = [
        migrations.RunPython(ensure_profiles_have_orgs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="vendorprofile",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="profiles",
                to="vendor_app.vendororg",
            ),
        ),
    ]


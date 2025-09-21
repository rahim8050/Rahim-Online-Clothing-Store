from django.db import migrations, models

ROLE_CHOICES = (
    ("customer", "Customer"),
    ("vendor", "Vendor"),
    ("vendor_staff", "Vendor Staff"),
    ("driver", "Driver"),
    ("admin", "Admin"),
)


def backfill_roles(apps, schema_editor):
    User = apps.get_model("users", "CustomUser")
    Group = apps.get_model("auth", "Group")
    VendorStaff = apps.get_model("users", "VendorStaff")

    # Preload group names -> ids
    group_names = {"Vendor": None, "Vendor Staff": None, "Driver": None}
    for name in list(group_names.keys()):
        try:
            g = Group.objects.get(name=name)
            group_names[name] = g.id
        except Group.DoesNotExist:
            group_names[name] = None

    # Admins
    User.objects.filter(models.Q(is_superuser=True) | models.Q(is_staff=True)).update(role="admin")

    # Vendors (via Group membership)
    if group_names.get("Vendor"):
        # The m2m through table name is historical; use the reverse manager to avoid hardcoding.
        try:
            vendor_group = Group.objects.get(pk=group_names["Vendor"])  # re-fetch
            for u in vendor_group.user_set.only("id").iterator(chunk_size=2000):
                User.objects.filter(pk=u.pk, role__in=[None, "", "customer"]).update(role="vendor")
        except Exception:
            pass

    # Vendor Staff (via relation if present)
    try:
        staff_ids = (
            VendorStaff.objects.filter(is_active=True).values_list("staff_id", flat=True).distinct()
        )
        # Use batched updates to avoid IN too large
        batch = []
        for sid in staff_ids:
            batch.append(sid)
            if len(batch) >= 1000:
                User.objects.filter(pk__in=batch).exclude(role="admin").update(role="vendor_staff")
                batch = []
        if batch:
            User.objects.filter(pk__in=batch).exclude(role="admin").update(role="vendor_staff")
    except Exception:
        pass

    # Drivers (via Group membership)
    if group_names.get("Driver"):
        try:
            driver_group = Group.objects.get(pk=group_names["Driver"])  # re-fetch
            for u in driver_group.user_set.only("id").iterator(chunk_size=2000):
                # do not override admin or vendor/vendor_staff already set unless they were default
                User.objects.filter(pk=u.pk).exclude(
                    role__in=["admin", "vendor", "vendor_staff"]
                ).update(role="driver")
        except Exception:
            pass

    # Remaining users -> ensure at least 'customer'
    User.objects.filter(models.Q(role__isnull=True) | models.Q(role="")).update(role="customer")


def unbackfill_roles(apps, schema_editor):
    User = apps.get_model("users", "CustomUser")
    # Safe fallback on reverse: set any blank/invalid to 'customer'
    User.objects.filter(models.Q(role__isnull=True) | models.Q(role="")).update(role="customer")


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0005_vendorstaff_scopes"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="role",
            field=models.CharField(
                blank=True, choices=ROLE_CHOICES, default="customer", max_length=32
            ),
        ),
        migrations.RunPython(backfill_roles, unbackfill_roles),
    ]

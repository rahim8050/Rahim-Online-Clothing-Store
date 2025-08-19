from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    VendorStaff = apps.get_model("users", "VendorStaff")
    now = timezone.now()
    VendorStaff.objects.filter(status="accepted", accepted_at__isnull=True).update(accepted_at=now)
    VendorStaff.objects.filter(status="accepted").update(is_active=True)
    VendorStaff.objects.exclude(status="accepted").update(is_active=False)


def backwards(apps, schema_editor):
    VendorStaff = apps.get_model("users", "VendorStaff")
    VendorStaff.objects.exclude(status="accepted").update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_vendorstaff_schema_hardening"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

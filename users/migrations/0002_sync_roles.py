from django.db import migrations


def forwards(apps, schema_editor):
    from users.roles import sync_roles

    sync_roles()


def reverse(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    roles = [
        "Admin",
        "Customer",
        "Vendor",
        "Vendor Staff",
        "Driver",
    ]
    Group.objects.filter(name__in=roles).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, reverse)]

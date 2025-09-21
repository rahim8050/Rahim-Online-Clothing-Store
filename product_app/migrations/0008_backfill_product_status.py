from django.db import migrations


def backfill(apps, schema_editor):
    Product = apps.get_model("product_app", "Product")
    # Ensure any NULL/empty values are set to a safe default
    try:
        Product.objects.filter(status__isnull=True).update(status="active")
    except Exception:
        # If field type differs unexpectedly, be forgiving
        pass
    try:
        Product.objects.filter(status="").update(status="active")
    except Exception:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("product_app", "0007_product_status"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]

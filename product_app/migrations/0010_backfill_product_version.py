from django.db import migrations


def backfill(apps, schema_editor):
    Product = apps.get_model("product_app", "Product")
    Product.objects.filter(version__isnull=True).update(version=1)


class Migration(migrations.Migration):
    dependencies = [
        ("product_app", "0009_product_version_column"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]

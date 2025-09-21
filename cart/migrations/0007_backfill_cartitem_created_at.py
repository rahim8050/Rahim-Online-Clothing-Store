from django.db import migrations
from django.utils import timezone


def backfill(apps, schema_editor):
    CartItem = apps.get_model("cart", "CartItem")
    CartItem.objects.filter(created_at__isnull=True).update(created_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0006_alter_cart_created_at_alter_cartitem_created_at"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]

from django.db import migrations


def drop_status_if_exists(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor
    table = "product_app_product"
    try:
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(cursor, table)
            cols = {getattr(c, "name", None) or c[0] for c in desc}
    except Exception:
        cols = set()
    if "status" not in cols:
        return
    try:
        if vendor == "mysql":
            schema_editor.execute("ALTER TABLE `product_app_product` DROP COLUMN `status`")
        elif vendor == "postgresql":
            schema_editor.execute(
                'ALTER TABLE "product_app_product" DROP COLUMN IF EXISTS "status"'
            )
        elif vendor == "sqlite":
            # SQLite < 3.35 cannot drop columns easily; skip to avoid destructive changes.
            # On SQLite dev, table likely doesn't have this column.
            pass
        else:
            # Fallback attempt
            schema_editor.execute("ALTER TABLE product_app_product DROP COLUMN status")
    except Exception:
        # Non-fatal: leave DB as-is rather than breaking migrations
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("product_app", "0005_product_product_version"),
    ]

    operations = [
        migrations.RunPython(drop_status_if_exists, migrations.RunPython.noop),
    ]

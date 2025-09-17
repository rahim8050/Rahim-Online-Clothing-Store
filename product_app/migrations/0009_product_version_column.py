from django.db import migrations, models


def ensure_version_column(apps, schema_editor):
    connection = schema_editor.connection
    table = 'product_app_product'
    vendor = connection.vendor
    has_col = False
    try:
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(cursor, table)
            cols = {getattr(c, 'name', None) or c[0] for c in desc}
            has_col = 'version' in cols
    except Exception:
        has_col = False

    with connection.cursor() as cursor:
        if vendor == 'mysql':
            if has_col:
                cursor.execute("ALTER TABLE `product_app_product` MODIFY COLUMN `version` INT NOT NULL DEFAULT 1")
            else:
                cursor.execute("ALTER TABLE `product_app_product` ADD COLUMN `version` INT NOT NULL DEFAULT 1")
        elif vendor == 'postgresql':
            if has_col:
                cursor.execute('ALTER TABLE "product_app_product" ALTER COLUMN "version" SET DEFAULT 1')
                cursor.execute('ALTER TABLE "product_app_product" ALTER COLUMN "version" SET NOT NULL')
            else:
                cursor.execute('ALTER TABLE "product_app_product" ADD COLUMN "version" integer NOT NULL DEFAULT 1')
        else:  # sqlite or others
            if not has_col:
                cursor.execute('ALTER TABLE "product_app_product" ADD COLUMN "version" integer DEFAULT 1 NOT NULL')
            # If exists, SQLite cannot easily alter; leave as-is.


class Migration(migrations.Migration):
    dependencies = [
        ("product_app", "0008_backfill_product_status"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(ensure_version_column, migrations.RunPython.noop)],
            state_operations=[
                migrations.AddField(
                    model_name='product',
                    name='version',
                    field=models.PositiveIntegerField(default=1),
                ),
            ],
        )
    ]


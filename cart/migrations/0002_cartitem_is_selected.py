# cart/migrations/00XX_safe_add_is_selected.py
from django.db import migrations


def _column_names(schema_editor, table: str) -> set[str]:
    with schema_editor.connection.cursor() as cursor:
        if schema_editor.connection.vendor == "sqlite":
            cursor.execute(f"PRAGMA table_info({table})")
            return {row[1] for row in cursor.fetchall()}
        return {
            c.name
            for c in schema_editor.connection.introspection.get_table_description(
                cursor, table
            )
        }


def add_is_selected(apps, schema_editor):
    CartItem = apps.get_model("cart", "CartItem")
    table = CartItem._meta.db_table
    if "is_selected" in _column_names(schema_editor, table):
        return
    field = CartItem._meta.get_field("is_selected")
    schema_editor.add_field(CartItem, field)


def remove_is_selected(apps, schema_editor):
    CartItem = apps.get_model("cart", "CartItem")
    table = CartItem._meta.db_table
    if "is_selected" not in _column_names(schema_editor, table):
        return
    field = CartItem._meta.get_field("is_selected")
    schema_editor.remove_field(CartItem, field)


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0001_initial"),  # replace with your latest dependency
    ]

    operations = [migrations.RunPython(add_is_selected, remove_is_selected)]

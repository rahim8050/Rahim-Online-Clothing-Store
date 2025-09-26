# cart/migrations/00XX_safe_add_is_selected.py
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0001_initial"),  # replace with your latest dependency
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE cart_cartitem "
                "ADD COLUMN IF NOT EXISTS is_selected boolean NOT NULL DEFAULT true;"
            ),
            reverse_sql=(
                "ALTER TABLE cart_cartitem DROP COLUMN IF EXISTS is_selected;"
            ),
        ),
    ]

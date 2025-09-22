from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product_app", "0006_cleanup_product_status_column"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="status",
            field=models.CharField(
                max_length=20,
                choices=[("draft", "Draft"), ("active", "Active"), ("archived", "Archived")],
                default="active",
                db_index=True,
            ),
            preserve_default=True,
        ),
    ]

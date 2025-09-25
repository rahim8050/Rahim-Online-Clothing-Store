from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_vendorapplication_document_vendorapplication_kra_pin_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendorstaff",
            name="scopes",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

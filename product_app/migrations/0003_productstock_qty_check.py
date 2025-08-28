from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product_app", "0002_product_owner"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="productstock",
            constraint=models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name="productstock_quantity_gte_0",
            ),
        ),
    ]

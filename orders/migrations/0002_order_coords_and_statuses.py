from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="coords_locked",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="order",
            name="coords_source",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="order",
            name="coords_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="orderitem",
            name="delivery_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("dispatched", "Dispatched"),
                    ("en_route", "En route"),
                    ("nearby", "Nearby"),
                    ("delivered", "Delivered"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                    ("compromised", "Compromised"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]

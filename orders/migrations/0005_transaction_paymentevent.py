from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "orders",
            "0004_rename_delivery_order_status_idx_orders_deli_order_i_2374e2_idx_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="status",
            field=models.CharField(
                choices=[
                    ("initialized", "Initialized"),
                    ("pending", "Pending"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                ],
                default="initialized",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="raw_event",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="processed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("provider", models.CharField(max_length=20)),
                ("reference", models.CharField(max_length=100)),
                ("body", models.JSONField()),
                ("body_sha256", models.CharField(max_length=64, unique=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["provider", "reference"],
                        name="orders_paym_provider_ref_idx",
                    )
                ],
            },
        ),
    ]

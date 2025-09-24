from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0006_transaction_commission_amount_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReconcileIdempotency",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name="ID")),
                ("key", models.CharField(max_length=200, unique=True)),
                ("executed_at", models.DateTimeField(null=True, blank=True)),
                ("result_json", models.JSONField(default=dict, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "payments_idempotency",
                "indexes": [
                    models.Index(fields=["created_at"], name="payments_idem_created_at_idx"),
                ],
            },
        ),
    ]

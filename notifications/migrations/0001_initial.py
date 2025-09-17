from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=200)),
                ("message", models.TextField()),
                (
                    "level",
                    models.CharField(
                        max_length=10,
                        choices=[
                            ("info", "Info"),
                            ("success", "Success"),
                            ("warning", "Warning"),
                            ("error", "Error"),
                        ],
                        default="info",
                    ),
                ),
                ("url", models.CharField(max_length=300, blank=True)),
                ("read_at", models.DateTimeField(null=True, blank=True, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["user", "read_at"],
                name="notif_user_read_idx",
            ),
        ),
    ]

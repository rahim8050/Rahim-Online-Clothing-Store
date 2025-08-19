from django.db import migrations, models
from django.db.models import Q, F


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="vendorstaff",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "pending"),
                    ("accepted", "accepted"),
                    ("disabled", "disabled"),
                ],
                default="pending",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="vendorstaff",
            name="is_active",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="vendorstaff",
            name="invited_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="vendorstaff",
            name="accepted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="vendorstaff",
            name="last_emailed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="vendorstaff",
            constraint=models.UniqueConstraint(
                fields=["owner", "staff"], name="uniq_owner_staff"
            ),
        ),
        migrations.AddConstraint(
            model_name="vendorstaff",
            constraint=models.CheckConstraint(
                check=~Q(owner=F("staff")), name="no_self_membership"
            ),
        ),
        migrations.AddIndex(
            model_name="vendorstaff",
            index=models.Index(fields=["owner", "is_active"], name="users_vendorstaff_owner_is_active_idx"),
        ),
        migrations.AddIndex(
            model_name="vendorstaff",
            index=models.Index(fields=["staff", "is_active"], name="users_vendorstaff_staff_is_active_idx"),
        ),
        migrations.AddIndex(
            model_name="vendorstaff",
            index=models.Index(fields=["status"], name="users_vendorstaff_status_idx"),
        ),
    ]

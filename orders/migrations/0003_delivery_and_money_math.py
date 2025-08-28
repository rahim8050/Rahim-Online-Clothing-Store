from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from django.db.models import Q
import uuid


def uuid_hex():
    return uuid.uuid4().hex


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_order_dest_address_text_order_dest_lat_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orderitem",
            name="delivery_status",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("dispatched", "Dispatched"),
                    ("en_route", "En route"),
                    ("delivered", "Delivered"),
                ],
                db_index=True,
                default="created",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="orderitem",
            index=models.Index(fields=["order", "product"], name="orderitem_order_product_idx"),
        ),
        migrations.CreateModel(
            name="Delivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("assigned", "Assigned"),
                            ("picked_up", "Picked up"),
                            ("en_route", "En route"),
                            ("delivered", "Delivered"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("assigned_at", models.DateTimeField(blank=True, null=True)),
                ("picked_up_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("origin_lat", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("origin_lng", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("dest_lat", models.DecimalField(decimal_places=6, max_digits=9)),
                ("dest_lng", models.DecimalField(decimal_places=6, max_digits=9)),
                ("last_lat", models.FloatField(blank=True, null=True)),
                ("last_lng", models.FloatField(blank=True, null=True)),
                ("last_ping_at", models.DateTimeField(blank=True, null=True)),
                ("channel_key", models.CharField(default=uuid_hex, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "driver",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="deliveries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="orders.order",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["order", "status"], name="delivery_order_status_idx"),
                    models.Index(fields=["driver", "status"], name="delivery_driver_status_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="delivery",
            constraint=models.CheckConstraint(
                name="delivery_driver_required_when_moving",
                check=Q(status__in=["pending", "delivered", "cancelled"]) | Q(driver__isnull=False),
            ),
        ),
        migrations.AddConstraint(
            model_name="delivery",
            constraint=models.CheckConstraint(
                name="delivery_dest_lat_range",
                check=Q(dest_lat__gte=-90) & Q(dest_lat__lte=90),
            ),
        ),
        migrations.AddConstraint(
            model_name="delivery",
            constraint=models.CheckConstraint(
                name="delivery_dest_lng_range",
                check=Q(dest_lng__gte=-180) & Q(dest_lng__lte=180),
            ),
        ),
        migrations.AddConstraint(
            model_name="delivery",
            constraint=models.CheckConstraint(
                name="delivery_origin_lat_range",
                check=Q(origin_lat__isnull=True) | (Q(origin_lat__gte=-90) & Q(origin_lat__lte=90)),
            ),
        ),
        migrations.AddConstraint(
            model_name="delivery",
            constraint=models.CheckConstraint(
                name="delivery_origin_lng_range",
                check=Q(origin_lng__isnull=True) | (Q(origin_lng__gte=-180) & Q(origin_lng__lte=180)),
            ),
        ),
    ]

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0004_add_user_and_status"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="cart",
            constraint=models.UniqueConstraint(
                name="uniq_active_cart_per_user",
                fields=["user", "status"],
                condition=Q(status="active"),
            ),
        ),
    ]

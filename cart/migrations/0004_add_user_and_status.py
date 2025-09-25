import django.db.models.deletion
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cart", "0003_alter_cartitem_is_selected"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Cart fields
        migrations.AddField(
            model_name="cart",
            name="user",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="carts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="cart",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("ordered", "Ordered"),
                    ("abandoned", "Abandoned"),
                ],
                db_index=True,
                default="active",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="cart",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        # CartItem changes
        migrations.AlterField(
            model_name="cartitem",
            name="product",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cart_items",
                to="product_app.product",
            ),
        ),
        migrations.AlterField(
            model_name="cartitem",
            name="quantity",
            field=models.PositiveIntegerField(
                default=1, validators=[MinValueValidator(1)]
            ),
        ),
        migrations.AddField(
            model_name="cartitem",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "product"), name="uniq_product_per_cart"
            ),
        ),
    ]

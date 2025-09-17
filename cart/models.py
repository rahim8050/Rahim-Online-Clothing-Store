from django.db import models
from django.db.models import Sum, Q
from django.core.validators import MinValueValidator
from django.conf import settings
from product_app.models import Product
from orders.money import D
from django.utils import timezone

class Cart(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ORDERED = "ordered", "Ordered"
        ABANDONED = "abandoned", "Abandoned"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total_price(self):
        """Return the total price for all items as a Decimal."""
        return sum((item.get_total_price() for item in self.items.all()), D("0.00"))

    def get_selected_total_price(self):
        """Return the total price for only selected items as a Decimal."""
        return sum(
            (item.get_total_price() for item in self.items.filter(is_selected=True)),
            D("0.00"),
        )

    def total_items(self):
        return self.items.aggregate(
            total=Sum('quantity')
        )['total'] or 0

    def __str__(self):
        return f"Cart #{self.id}"

    class Meta:
        constraints = [
            # Enforce one active cart per user (when user is set). Not all DBs support this; v2 logic also enforces at app level.
            models.UniqueConstraint(
                fields=["user", "status"],
                name="uniq_active_cart_per_user",
                condition=Q(status="active"),
            )
        ]


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        related_name='items',
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product,
        related_name='cart_items',
        default=None,
        on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    is_selected = models.BooleanField(default=False)


    def get_total_price(self):
        """Cost of this cart item (price * quantity) as a Decimal."""
        return D(self.product.price) * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="uniq_product_per_cart")
        ]

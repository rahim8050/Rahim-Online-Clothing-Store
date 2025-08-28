from django.db import models
from django.db.models import Sum
from product_app.models import Product
from orders.money import D


class Cart(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
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
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=1)
    is_selected = models.BooleanField(default=False)


    def get_total_price(self):
        """Cost of this cart item (price * quantity) as a Decimal."""
        return D(self.product.price) * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

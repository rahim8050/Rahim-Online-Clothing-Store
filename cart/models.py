from django.db import models
from django.db.models import Sum
from product_app.models import Product
from django.contrib.auth.models import User
from users.models import CustomUser
from decimal import Decimal, ROUND_HALF_UP


class Cart(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total_price(self):
        # Sum the price for each CartItem
        return sum(item.get_total_price() for item in self.items.all())
    
    def get_selected_total_price(self):
        # Sum the price for only selected CartItems
        return sum(item.get_total_price() for item in self.items.filter(is_selected=True))

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

    def get_selected_total(self, selected_ids):
     return sum(item.product.price * item.quantity for item in self.items.filter(product_id__in=selected_ids))


    def __str__(self):
        return f"{self.quantity} x {self.product.name}"
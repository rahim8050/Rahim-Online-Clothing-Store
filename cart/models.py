from django.db import models
from django.db.models import Sum

from product_app.models import Product
from django.contrib.auth.models import User
from users.models import CustomUser,CartItem,Product


# models.py
class Cart(models.Model):
    # user = models.ForeignKey(CustomUser, related_name='carts', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total_price(self):
       return sum(item.get_total_price() for item in self.items.all())

    def total_items(self):

        return self.items.aggregate(
            total=Sum('quantity')
        )['total'] or 0


# class Cart(models.Model):
#    created_at = models.DateTimeField(auto_now_add=True)
#    updated_at = models.DateTimeField(auto_now=True)
#    def get_total_price(self):
#        return sum(item.get_total_price() for item in self.items.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart,related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="cart_items",default=None,on_delete=models.CASCADE)

    quantity = models.PositiveIntegerField(default=1)
    def get_total_price(self):
        return self.product.price * self.quantity

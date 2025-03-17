from django.db import models
from django.db.models import Sum
# Example: Import in another app's views.py
from product_app.models import Product

class Cart(models.Model):
   created_at = models.DateTimeField(auto_now_add=True)
   updated_at = models.DateTimeField(auto_now=True)
   def get_total_price(self):
       return self.cart.aggregate(total_price=Sum('price'))['total_price']

class CartItem(models.Model):
    cart = models.ForeignKey(Cart,related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="cart_items", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    def get_total_price(self):
        return self.product.price * self.quantity

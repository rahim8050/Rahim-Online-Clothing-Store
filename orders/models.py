from django.db import models
from product_app.models import Product
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

class Order(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)
    mpesa_checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    mpesa_phone_number = models.CharField(max_length=15, blank=True, null=True)
    mpesa_transaction_code = models.CharField(max_length=50, blank=True, null=True)
    payment_method = models.CharField(max_length=20, default="MPESA")
    stock_updated = models.BooleanField(default=False)



    def get_total_cost(self):
        return int(sum(item.get_cost() for item in self.items.all()))

    def __str__(self):
        return f"Order #{self.id} for {self.full_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def get_cost(self):
        return int(self.price * self.quantity)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

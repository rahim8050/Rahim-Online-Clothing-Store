from django.db import models
from product_app.models import Product, Warehouse
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

class Order(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_address = models.TextField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)
    # MPESA specific fields
    mpesa_checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    mpesa_phone_number = models.CharField(max_length=15, blank=True, null=True)
    mpesa_transaction_code = models.CharField(max_length=50, blank=True, null=True)
    payment_method = models.CharField(max_length=20, default="MPESA")
    stock_updated = models.BooleanField(default=False)
    # stripe specific fields
    payment_status = models.CharField(max_length=20, default='pending')
    payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_receipt_url = models.URLField(blank=True, null=True)



    def get_total_cost(self):
        return int(sum(item.get_cost() for item in self.items.all()))

    def __str__(self):
        return f"Order #{self.id} for {self.full_name}"


class OrderItem(models.Model):
    DELIVERY_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("dispatched", "Dispatched"),
        ("in_transit", "In transit"),
        ("delivered", "Delivered"),
    ]

    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    warehouse = models.ForeignKey(
        Warehouse, null=True, blank=True, on_delete=models.SET_NULL
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default="pending",
    )

    def get_cost(self):
        return int(self.price * self.quantity)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


class Transaction(models.Model):
    METHOD_CHOICES = (
        ("card", "Card"),
        ("mpesa", "M-Pesa"),
        ("paypal", "PayPal"),
    )

    GATEWAY_CHOICES = (
        ("paystack", "Paystack"),
        ("daraja", "Daraja"),
        ("paypal", "PayPal"),
    )

    STATUS_CHOICES = (
        ("unknown", "Unknown"),     
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    email = models.EmailField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    gateway = models.CharField(max_length=10, choices=GATEWAY_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="unknown"
    )
    callback_received = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    reference = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.method} - {self.reference}"

class EmailDispatchLog(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    status = models.CharField(max_length=10)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
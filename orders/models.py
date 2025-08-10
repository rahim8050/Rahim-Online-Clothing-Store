from django.db import models
from django.db.models import CheckConstraint, Q
from django.contrib.auth import get_user_model
from django.conf import settings
from product_app.models import Product, Warehouse

User = get_user_model()

class Order(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_address = models.TextField(null=True, blank=True)
    coords_locked = models.BooleanField(default=False)
    coords_source = models.CharField(max_length=20, blank=True, default="")
    coords_updated_at = models.DateTimeField(null=True, blank=True)

    # Destination selected via Geoapify autocomplete
    dest_address_text = models.CharField(max_length=255)
    dest_lat = models.DecimalField(max_digits=9, decimal_places=6)
    dest_lng = models.DecimalField(max_digits=9, decimal_places=6)
    dest_source = models.CharField(max_length=32, default="autocomplete")
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

    class Meta:
        constraints = [
            CheckConstraint(
                check=(Q(latitude__gte=-90) & Q(latitude__lte=90)) | Q(latitude__isnull=True),
                name="order_lat_range",
            ),
            CheckConstraint(
                check=(Q(longitude__gte=-180) & Q(longitude__lte=180)) | Q(longitude__isnull=True),
                name="order_lng_range",
            ),
            CheckConstraint(
                check=(
                    (Q(latitude__gte=-90) & Q(latitude__lte=90) &
                     Q(longitude__gte=-180) & Q(longitude__lte=180)) |
                    (Q(latitude__isnull=True) & Q(longitude__isnull=True))
                ),
                name="order_lat_lng_range_or_null",
            ),
            CheckConstraint(
                name="order_dest_lat_range",
                check=Q(dest_lat__gte=-90) & Q(dest_lat__lte=90),
            ),
            CheckConstraint(
                name="order_dest_lng_range",
                check=Q(dest_lng__gte=-180) & Q(dest_lng__lte=180),
            ),
        ]

    def get_total_cost(self):
        return int(sum(item.get_cost() for item in self.items.all()))

    def __str__(self):
        return f"Order #{self.id} for {self.full_name}"


class OrderItem(models.Model):
    DELIVERY_STATUS_CHOICES = [
        ("created", "Created"),
        ("dispatched", "Dispatched"),
        ("en_route", "En route"),
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
        default="created",
    )

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(delivery_status='created') | Q(warehouse__isnull=False),
                name="item_requires_warehouse_when_moving",
            ),
        ]

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
    verified = models.BooleanField(default=False)
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

from uuid import uuid4
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import CheckConstraint, Index, Q
from django.utils import timezone

from product_app.models import Product, Warehouse


# 6-decimal quantum for geo coordinates
Q6 = Decimal("0.000001")


# =========================
# Orders
# =========================
class Order(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.CharField(max_length=250)

    # (Optional) caller-provided coords — keep nullable
    latitude  = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_address = models.TextField(null=True, blank=True)
    coords_locked = models.BooleanField(default=False)
    coords_source = models.CharField(max_length=20, blank=True, default="")
    coords_updated_at = models.DateTimeField(null=True, blank=True)

    # Destination selected via Geoapify autocomplete (REQUIRED)
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

    # Stripe specific fields
    payment_status = models.CharField(max_length=20, default="pending")
    payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_receipt_url = models.URLField(blank=True, null=True)

    class Meta:
        constraints = [
            # latitude/longitude either both NULL or both in range
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
                     Q(longitude__gte=-180) & Q(longitude__lte=180))
                    | (Q(latitude__isnull=True) & Q(longitude__isnull=True))
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
        indexes = [
            Index(fields=["created_at"]),
            Index(fields=["updated_at"]),
        ]

    def save(self, *args, **kwargs):
        # normalize decimals to 6 dp
        for f in ("latitude", "longitude", "dest_lat", "dest_lng"):
            v = getattr(self, f, None)
            if v is not None:
                setattr(self, f, Decimal(v).quantize(Q6, rounding=ROUND_HALF_UP))
        super().save(*args, **kwargs)

    def get_total_cost(self):
        return sum((item.get_cost() for item in self.items.all()), Decimal("0"))

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
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    quantity = models.PositiveIntegerField(default=1)
    warehouse = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.SET_NULL)
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default="created",
        db_index=True,
    )

    class Meta:
        constraints = [
            # once moving (not 'created'), a warehouse must be set
            CheckConstraint(
                check=Q(delivery_status="created") | Q(warehouse__isnull=False),
                name="item_requires_warehouse_when_moving",
            ),
        ]
        indexes = [
            Index(fields=["order", "product"]),
        ]

    def get_cost(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


# =========================
# Delivery
# =========================
def channel_key_default() -> str:
    return uuid4().hex  # 32 chars


class Delivery(models.Model):
    class Status(models.TextChoices):
        PENDING   = "pending", "Pending"
        ASSIGNED  = "assigned", "Assigned"
        PICKED_UP = "picked_up", "Picked up"
        EN_ROUTE  = "en_route", "En route"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    order = models.ForeignKey("orders.Order", related_name="deliveries", on_delete=models.CASCADE)
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="deliveries",
        on_delete=models.SET_NULL,
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    assigned_at  = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    origin_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    origin_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    dest_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    dest_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    last_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    last_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    last_ping_at = models.DateTimeField(null=True, blank=True)

    channel_key = models.CharField(max_length=32, unique=True, default=channel_key_default, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # when "moving", driver must be set
            CheckConstraint(
                name="delivery_driver_required_when_moving",
                check=Q(status__in=["pending", "delivered", "cancelled"]) | Q(driver__isnull=False),
            ),
            # allow NULL or valid range for all coords
            CheckConstraint(
                name="delivery_dest_lat_range_or_null",
                check=Q(dest_lat__isnull=True) | (Q(dest_lat__gte=-90) & Q(dest_lat__lte=90)),
            ),
            CheckConstraint(
                name="delivery_dest_lng_range_or_null",
                check=Q(dest_lng__isnull=True) | (Q(dest_lng__gte=-180) & Q(dest_lng__lte=180)),
            ),
            CheckConstraint(
                name="delivery_origin_lat_range",
                check=Q(origin_lat__isnull=True) | (Q(origin_lat__gte=-90) & Q(origin_lat__lte=90)),
            ),
            CheckConstraint(
                name="delivery_origin_lng_range",
                check=Q(origin_lng__isnull=True) | (Q(origin_lng__gte=-180) & Q(origin_lng__lte=180)),
            ),
        ]
        indexes = [
            Index(fields=["order", "status"]),
            Index(fields=["driver", "status"]),
            Index(fields=["last_ping_at"]),
            Index(fields=["created_at"]),
            Index(fields=["updated_at"]),
        ]

    @property
    def ws_group(self) -> str:
        return f"delivery.{self.pk}"

    def snapshot_endpoints_from_order(self):
        self.dest_lat = self.order.dest_lat
        self.dest_lng = self.order.dest_lng
        item = self.order.items.select_related("warehouse").first()
        wh = getattr(item, "warehouse", None)
        if wh and getattr(wh, "latitude", None) is not None and getattr(wh, "longitude", None) is not None:
            self.origin_lat = wh.latitude
            self.origin_lng = wh.longitude

    def mark_assigned(self, driver):
        self.driver = driver
        self.status = self.Status.ASSIGNED
        self.assigned_at = timezone.now()

    def save(self, *args, **kwargs):
        for f in ("origin_lat", "origin_lng", "dest_lat", "dest_lng", "last_lat", "last_lng"):
            v = getattr(self, f, None)
            if v is not None:
                setattr(self, f, Decimal(v).quantize(Q6, rounding=ROUND_HALF_UP))
        super().save(*args, **kwargs)


# =========================
# Payments / Events
# =========================
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
        ("initialized", "Initialized"),
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    email = models.EmailField(blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    gateway = models.CharField(max_length=10, choices=GATEWAY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="initialized")
    callback_received = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    reference = models.CharField(max_length=100, unique=True)
    raw_event = models.JSONField(blank=True, null=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.method} - {self.reference}"


class EmailDispatchLog(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    status = models.CharField(max_length=10)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)


class PaymentEvent(models.Model):
    provider = models.CharField(max_length=20)
    reference = models.CharField(max_length=100)
    body = models.JSONField()
    body_sha256 = models.CharField(max_length=64, unique=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["provider", "reference"])]

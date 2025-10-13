from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q
from django.urls import reverse
from django.db.models import Sum


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.CASCADE
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="vendor_products",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    available = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    # Keep for DB compatibility (MySQL strict error 1364): ensure default exists
    version = models.PositiveIntegerField(default=1)
    product_version = models.PositiveIntegerField(default=1)
    image = models.ImageField(upload_to="products", blank=True, null=True)

    def total_stock(self):
        return self.stocks.aggregate(total=Sum("quantity"))["total"] or 0

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        return reverse(
            "product_app:product_detail", kwargs={"id": self.id, "slug": self.slug}
        )


class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    def clean(self) -> None:
        """Validate coordinates are within the global range and inside Kenya."""
        super().clean()
        if self.latitude is None or self.longitude is None:
            return
        if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
            raise ValidationError("Invalid latitude/longitude range.")
        if not (-4.8 <= self.latitude <= 5.3 and 33.5 <= self.longitude <= 42.2):
            raise ValidationError("Coordinates must be within Kenya’s boundaries.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(latitude__gte=-90) & Q(latitude__lte=90),
                name="warehouse_lat_range",
            ),
            CheckConstraint(
                check=Q(longitude__gte=-180) & Q(longitude__lte=180),
                name="warehouse_lng_range",
            ),
            CheckConstraint(
                check=Q(latitude__gte=-4.8)
                & Q(latitude__lte=5.3)
                & Q(longitude__gte=33.5)
                & Q(longitude__lte=42.2),
                name="warehouse_in_kenya_bbox",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ProductStock(models.Model):
    product = models.ForeignKey(
        Product, related_name="stocks", on_delete=models.CASCADE
    )
    warehouse = models.ForeignKey(
        Warehouse, related_name="stock_items", on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("product", "warehouse")
        constraints = [
            CheckConstraint(
                check=Q(quantity__gte=0), name="productstock_quantity_gte_0"
            )
        ]

    def __str__(self) -> str:
        return f"{self.product.name} - {self.warehouse.name}"

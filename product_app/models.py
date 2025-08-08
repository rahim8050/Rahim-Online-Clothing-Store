from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db.models import CheckConstraint, Q

# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    available = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to="products", blank=True, null=True)

    def __str__(self):
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

    def clean(self):
        super().clean()

        if self.latitude is None or self.longitude is None:
            return

        # Generic lat/lng range check
        if not (-90 <= self.latitude <= 90 and -180 <= self.longitude <= 180):
            raise ValidationError("Invalid latitude/longitude range.")

        # Kenya-only bounding box (approximate)
        # Covers from the southernmost point (≈ -4.68) to the northernmost (≈ 5.2)
        # and from the westernmost point (≈ 33.9) to the easternmost (≈ 41.9)
        if not (-4.8 <= self.latitude <= 5.3 and 33.5 <= self.longitude <= 42.2):
            raise ValidationError("Coordinates must be within Kenya’s boundaries.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Ensures clean() runs even outside ModelForms
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            CheckConstraint(
                check=Q(latitude__gte=-90) & Q(latitude__lte=90),
                name="wh_lat_range",
            ),
            CheckConstraint(
                check=Q(longitude__gte=-180) & Q(longitude__lte=180),
                name="wh_lng_range",
            ),
        ]
    class Meta:
       constraints = [
        CheckConstraint(check=Q(latitude__gte=-90) & Q(latitude__lte=90), name="wh_lat_range"),
        CheckConstraint(check=Q(longitude__gte=-180) & Q(longitude__lte=180), name="wh_lng_range"),
        CheckConstraint(
            check=Q(latitude__gte=-4.8) & Q(latitude__lte=5.3) &
                  Q(longitude__gte=33.5) & Q(longitude__lte=42.2),
            name="wh_in_kenya_bbox",
        ),
    ]    

    def __str__(self):
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

    def __str__(self):
        return f"{self.product.name} - {self.warehouse.name}"



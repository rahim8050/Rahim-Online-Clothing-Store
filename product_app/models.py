from django.db import models
from django.conf import settings
from  django.urls import reverse
# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    class Meta:
        verbose_name_plural = 'categories'
    def __str__(self):
        return self.name
class Product(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        AWAITING_PUBLICATION = "AWAITING_PUBLICATION", "Awaiting Publication"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.CASCADE
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="products", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    available = models.BooleanField(default=True)
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.DRAFT
    )
    version = models.PositiveIntegerField(default=1)
    published_version = models.PositiveIntegerField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to="products", blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gte=0), name="product_price_gte_0"
            )
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_app:detail", kwargs={"id": self.id, "slug": self.slug})

    def is_editable(self):
        return self.status != self.Status.ARCHIVED


class ListingCheckout(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        COMPLETED = "COMPLETED", "Completed"
        CANCELED = "CANCELED", "Canceled"
        SUPERSEDED = "SUPERSEDED", "Superseded"

    product = models.ForeignKey(
        Product, related_name="listing_checkouts", on_delete=models.CASCADE
    )
    product_version = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    gateway = models.CharField(max_length=50, blank=True)
    provider_ref = models.CharField(max_length=100, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="listing_checkouts", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Checkout {self.id} for {self.product_id}"


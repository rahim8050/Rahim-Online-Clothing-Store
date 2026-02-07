from django import forms
from django.contrib import admin
from django.db.models import Sum

from .models import Category, Product, ProductStock, Warehouse


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        status = self.fields.get("status")
        if status is not None:
            status.required = False
            status.initial = Product.Status.ACTIVE
        product_version = self.fields.get("product_version")
        if product_version is not None:
            product_version.required = False
            product_version.initial = 1

    def clean_status(self):
        return self.cleaned_data.get("status") or Product.Status.ACTIVE

    def clean_product_version(self):
        return self.cleaned_data.get("product_version") or 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = [
        "name",
        "price",
        "category",
        "status",
        "available",
        "version",
        "total_stock",
    ]
    list_filter = ("status", "available", "category")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("version",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Annotate total stock across all warehouses for this product
        return qs.annotate(_total_stock=Sum("stocks__quantity"))

    def total_stock(self, obj):
        return obj._total_stock or 0

    total_stock.short_description = "Total stock"
    total_stock.admin_order_field = "_total_stock"


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["name", "latitude", "longitude"]


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ["product", "warehouse", "quantity"]

from django.contrib import admin
from django.db.models import Sum
from .models import Category, Product, Warehouse, ProductStock


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "category", "status", "available", "version", "total_stock"]
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

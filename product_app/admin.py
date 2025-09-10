from django.contrib import admin
from .models import Category, Product, Warehouse, ProductStock


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "category", "status", "available", "version"]
    list_filter = ("status", "available", "category")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("version",)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["name", "latitude", "longitude"]


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ["product", "warehouse", "quantity"]

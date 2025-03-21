from django.contrib import admin

from orders.models import Order, OrderItem


# Register your models here.
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ["product"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "full_name", "email"]
    inlines = [OrderItemInline]
    readonly_fields = ("created_at",)

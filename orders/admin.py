from django.contrib import admin

from orders.models import Order, OrderItem, Transaction


# Register your models here.
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ["product", "warehouse"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "full_name", "email"]
    inlines = [OrderItemInline]
    readonly_fields = ("created_at",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "method", "gateway", "status", "reference", "created_at")
    list_filter = ("method", "gateway", "status")

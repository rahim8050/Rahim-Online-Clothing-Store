from django.contrib import admin, messages

from .services.destinations import ensure_order_coords
from orders.models import Order, OrderItem, Transaction

@admin.action(description="Geocode destination (missing only)")
def geocode_destination(modeladmin, request, queryset):
    updated = 0
    for order in queryset:
        if order.latitude is not None and order.longitude is not None:
            continue
        try:
            if ensure_order_coords(order):
                updated += 1
        except Exception as exc:  # pragma: no cover - defensive
            modeladmin.message_user(request, f"{order.id}: {exc}", level=messages.WARNING)
    modeladmin.message_user(request, f"Geocoded {updated} orders.")

# Register your models here.
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ["product", "warehouse"]

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    actions = [geocode_destination]
    list_display = ["id", "full_name", "email"]
    inlines = [OrderItemInline]
    readonly_fields = ("created_at",)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "method", "gateway", "status", "reference", "created_at")
    list_filter = ("method", "gateway", "status")

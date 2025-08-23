from django.contrib import admin
from .models import Delivery


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "driver",
        "status",
        "assigned_at",
        "picked_up_at",
        "delivered_at",
        "last_lat",
        "last_lng",
        "last_ping_at",
        "updated_at",
    )
    list_filter = (
        "status",
        "assigned_at",
        "picked_up_at",
        "delivered_at",
        "last_ping_at",
    )
    search_fields = (
        "id",
        "order__id",
        "order__full_name",
        "driver__username",
        "driver__email",
    )
    autocomplete_fields = ("order", "driver")
    readonly_fields = ("created_at", "updated_at", "channel_key")


from django.contrib import admin
from .models import Delivery, DeliveryPing, DeliveryEvent


@admin.register(DeliveryPing)
class DeliveryPingAdmin(admin.ModelAdmin):
    list_display = ("id", "delivery", "lat", "lng", "created_at")
    list_filter = ("created_at",)
    search_fields = ("delivery__id",)


@admin.register(DeliveryEvent)
class DeliveryEventAdmin(admin.ModelAdmin):
    list_display = ("id", "delivery", "type", "actor", "at")
    list_filter = ("type", "at")
    search_fields = ("delivery__id", "actor__username")


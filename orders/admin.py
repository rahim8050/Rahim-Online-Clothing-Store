# orders/admin.py
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.contrib import admin, messages
from django.core.validators import MinValueValidator, MaxValueValidator

from .models import Order, Delivery, DeliveryPing, DeliveryEvent
from .services import assign_warehouses_and_update_stock

Q6 = Decimal("0.000001")


# ------------ PINGS / EVENTS ------------

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


# ------------ ORDER ------------

class OrderAdminForm(forms.ModelForm):
    # Allow very long inputs; we round to 6 dp in clean()
    latitude = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    dest_lat = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    dest_lng = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )

    class Meta:
        model = Order
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        for f in ("latitude", "longitude", "dest_lat", "dest_lng"):
            v = cleaned.get(f)
            if v is not None:
                cleaned[f] = Decimal(v).quantize(Q6, rounding=ROUND_HALF_UP)
        return cleaned


# ------------ DELIVERY ------------

class DeliveryAdminForm(forms.ModelForm):
    origin_lat = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    origin_lng = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    dest_lat = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    dest_lng = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    last_lat = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    last_lng = forms.DecimalField(
        max_digits=30, decimal_places=24, required=False,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )

    class Meta:
        model = Delivery
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        for f in ("origin_lat", "origin_lng", "dest_lat", "dest_lng", "last_lat", "last_lng"):
            v = cleaned.get(f)
            if v is not None:
                cleaned[f] = Decimal(v).quantize(Q6, rounding=ROUND_HALF_UP)
        return cleaned


# ------------ ADMINS ------------

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = ("id", "full_name", "email", "paid", "stock_updated", "created_at")
    list_filter = ("paid", "created_at")
    search_fields = ("=id", "full_name", "email", "address")
    ordering = ("-created_at",)

    actions = ["action_assign_and_reserve_stock"]

    def action_assign_and_reserve_stock(self, request, queryset):
        """
        Admin action: assign nearest warehouses and reserve (decrement) stock.
        """
        success, errors = 0, 0
        for order in queryset:
            try:
                assign_warehouses_and_update_stock(order)
                success += 1
            except Exception as e:
                errors += 1
        if success:
            messages.success(request, f"Assigned + reserved stock for {success} order(s).")
        if errors:
            messages.warning(request, f"{errors} order(s) failed to reserve stock (see logs).")

    action_assign_and_reserve_stock.short_description = "Assign warehouses + reserve stock"


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    form = DeliveryAdminForm
    list_display = (
        "id", "order", "driver", "status",
        "assigned_at", "picked_up_at", "delivered_at",
        "last_lat", "last_lng", "last_ping_at", "updated_at",
    )
    list_filter = ("status", "assigned_at", "picked_up_at", "delivered_at", "last_ping_at")
    search_fields = ("=id", "=order__id", "order__full_name", "driver__username", "driver__email")
    autocomplete_fields = ("order", "driver")
    readonly_fields = ("created_at", "updated_at", "channel_key")
    list_select_related = ("order", "driver")
    ordering = ("-updated_at",)
    list_per_page = 50

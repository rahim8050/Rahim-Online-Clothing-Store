
from decimal import Decimal, ROUND_HALF_UP
from django import forms
from django.contrib import admin
from django.forms import NumberInput
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Order, Delivery

User = get_user_model()
Q6 = Decimal("0.000001")

# ------------ ORDER -------------
# --- ORDER ---
class OrderAdminForm(forms.ModelForm):
    # allow very long inputs; we'll round to 6dp in clean()
    latitude  = forms.DecimalField(max_digits=30, decimal_places=24, required=False,
                                   validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = forms.DecimalField(max_digits=30, decimal_places=24, required=False,
                                   validators=[MinValueValidator(-180), MaxValueValidator(180)])
    dest_lat  = forms.DecimalField(max_digits=30, decimal_places=24,
                                   validators=[MinValueValidator(-90), MaxValueValidator(90)])
    dest_lng  = forms.DecimalField(max_digits=30, decimal_places=24,
                                   validators=[MinValueValidator(-180), MaxValueValidator(180)])
    ...
    def clean(self):
        cleaned = super().clean()
        for f in ("latitude", "longitude", "dest_lat", "dest_lng"):
            v = cleaned.get(f)
            if v is not None:
                cleaned[f] = v.quantize(Q6, rounding=ROUND_HALF_UP)  # -> 6 dp
        return cleaned


# ------------ DELIVERY -------------
class DeliveryAdminForm(forms.ModelForm):
    origin_lat = forms.DecimalField(max_digits=30, decimal_places=24, required=False,
                                    validators=[MinValueValidator(-90), MaxValueValidator(90)])
    origin_lng = forms.DecimalField(max_digits=30, decimal_places=24, required=False,
                                    validators=[MinValueValidator(-180), MaxValueValidator(180)])
    dest_lat   = forms.DecimalField(max_digits=30, decimal_places=24, required=False,
                                    validators=[MinValueValidator(-90), MaxValueValidator(90)])
    dest_lng   = forms.DecimalField(max_digits=30, decimal_places=24, required=False,
                                    validators=[MinValueValidator(-180), MaxValueValidator(180)])
    last_lat   = forms.DecimalField(max_digits=30, decimal_places=24, required=False,
                                    validators=[MinValueValidator(-90), MaxValueValidator(90)])
    last_lng   = forms.DecimalField(max_digits=30, decimal_places=24, required=False,
                                    validators=[MinValueValidator(-180), MaxValueValidator(180)])
    ...
    def clean(self):
        cleaned = super().clean()
        for f in ("origin_lat","origin_lng","dest_lat","dest_lng","last_lat","last_lng"):
            v = cleaned.get(f)
            if v is not None:
                cleaned[f] = v.quantize(Q6, rounding=ROUND_HALF_UP)  # -> 6 dp
        return cleaned
        return cleaned


# ------------ ADMINS -------------
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = ("id", "full_name", "email", "paid", "created_at")
    list_filter  = ("paid", "created_at")
    search_fields = ("=id", "full_name", "email", "address")
    ordering = ("-created_at",)

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
    # date_hierarchy = "assigned_at"   # OK once MySQL TZ tables are installed
    ordering = ("-updated_at",)
    list_per_page = 50

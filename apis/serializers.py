# apis/serializers.py
from __future__ import annotations

import re
from typing import Optional, List, Dict

from django.apps import apps
from django.db import transaction
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from rest_framework import serializers

from product_app.models import Product, ProductStock, Warehouse
from product_app.utils import get_vendor_field
from orders.models import OrderItem
from users.models import VendorStaff, VendorApplication
from users.utils import resolve_vendor_owner_for
from users import services  # provide: add_or_activate_staff(owner, staff, role), deactivate_vendor_staff(...)

User = get_user_model()


# -----------------------
# Helpers
# -----------------------
def _orderitem_reverse_name() -> str:
    """
    Return the reverse name from Product -> OrderItem safely.
    Falls back to 'orderitem_set' if related_name is blank, and '' if disabled with '+'.
    """
    field = OrderItem._meta.get_field("product")
    rel_name = getattr(field.remote_field, "related_name", None)
    if rel_name == "+":
        return ""  # reverse disabled
    return rel_name or "orderitem_set"


# -----------------------
# Auth / Me
# -----------------------
class WhoAmISerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True, allow_null=True)
    role = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()

    def get_role(self, obj):
        try:
            return getattr(obj, "effective_role", None) or getattr(obj, "role", None) or "customer"
        except Exception:
            return "customer"

    def get_role_label(self, obj):
        code = self.get_role(obj)
        try:
            choices = dict(getattr(User, "Role").choices)
            return choices.get(code, code)
        except Exception:
            labels = {
                "customer": "Customer",
                "vendor": "Vendor",
                "vendor_staff": "Vendor Staff",
                "driver": "Driver",
                "admin": "Admin",
            }
            return labels.get(code, code)


# -----------------------
# Order / Product
# -----------------------
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "order", "product", "price", "quantity", "delivery_status"]


class ProductSerializer(serializers.ModelSerializer):
    # Compute reverse safely; don't assume 'order_items'
    order_items = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "price", "available", "order_items"]

    def get_order_items(self, obj):
        rev = _orderitem_reverse_name()
        if not rev:
            return []  # reverse disabled
        qs = getattr(obj, rev).select_related("order", "product").all()
        return OrderItemSerializer(qs, many=True).data


class ProductListSerializer(serializers.ModelSerializer):
    owned_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "price", "available", "slug", "owned_by_me"]

    def get_owned_by_me(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        field = get_vendor_field(Product)  # e.g. 'owner' or 'vendor'
        return getattr(obj, f"{field}_id", None) == user.id



class ProductOutSerializer(serializers.ModelSerializer):
    stocks = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price",
            "available",
            "category",
            "owner",
            "image",
            "created",
            "updated",
            "stocks",
        ]

    def get_stocks(self, obj):
        return list(
            ProductStock.objects.filter(product=obj).values("warehouse_id", "quantity")
        )

# -----------------------
# Delivery (model may be absent)
# -----------------------
class _EmptySerializer(serializers.Serializer):
    pass


try:
    DeliveryModel = apps.get_model("orders", "Delivery")
except LookupError:
    DeliveryModel = None

if DeliveryModel is not None:
    class DeliverySerializer(serializers.ModelSerializer):
        class Meta:
            model = DeliveryModel
            fields = "__all__"
else:
    DeliverySerializer = _EmptySerializer


class DeliveryAssignSerializer(serializers.Serializer):
    driver_id = serializers.IntegerField()


class DeliveryUnassignSerializer(serializers.Serializer):
    pass


class DeliveryStatusSerializer(serializers.Serializer):
    # Start as CharField; upgrade to ChoiceField at runtime if we can read choices
    status = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        if DeliveryModel is not None:
            try:
                field = DeliveryModel._meta.get_field("status")
                if getattr(field, "choices", None):
                    choices = [c[0] for c in field.choices]
            except Exception:
                pass
            if not choices and hasattr(DeliveryModel, "Status") and getattr(DeliveryModel.Status, "choices", None):
                choices = [c[0] for c in DeliveryModel.Status.choices]
        if choices:
            self.fields["status"] = serializers.ChoiceField(choices=choices)


# -----------------------
# Vendor product creation
#   Supports:
#   - owner_id (acting owner for vendor staff)
#   - sku/stock/warehouse_id OR stock_allocations=[{warehouse, quantity}]
# -----------------------
class _StockAllocationInput(serializers.Serializer):
    warehouse = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=0)


class VendorProductCreateSerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(required=False, write_only=True)
    sku = serializers.CharField(required=False, write_only=True, allow_blank=True)
    stock = serializers.IntegerField(required=False, write_only=True, min_value=0)
    warehouse_id = serializers.IntegerField(required=False, write_only=True)
    stock_allocations = _StockAllocationInput(many=True, required=False, write_only=True)
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "description", "price", "available",
            "category", "image",
            "owner_id", "sku", "stock", "warehouse_id", "stock_allocations",
        ]
        read_only_fields = ["id"]

    # --- helpers ---
    @staticmethod
    def _normalize_slug(provided_slug: str, provided_sku: str, provided_name: str) -> str:
        if provided_slug:
            return slugify(provided_slug)
        if provided_sku:
            return slugify(provided_sku)
        return slugify(provided_name or "")

    def validate(self, attrs):
        request = self.context["request"]

        # resolve acting owner
        owner_hint = attrs.pop("owner_id", None)
        try:
            attrs["_acting_owner_id"] = resolve_vendor_owner_for(request.user, owner_hint)
        except ValueError as e:
            raise serializers.ValidationError({"owner_id": str(e)})

        # slug
        slug_in = (attrs.get("slug") or "").strip()
        sku_in = (attrs.pop("sku", "") or "").strip()
        name_in = (attrs.get("name") or "").strip()
        slug_final = self._normalize_slug(slug_in, sku_in, name_in)
        if not slug_final:
            raise serializers.ValidationError({"slug": "Slug (or sku/name to derive it) is required."})
        if Product.objects.filter(slug=slug_final).exists():
            raise serializers.ValidationError({"slug": "A product with this slug already exists."})
        attrs["slug"] = slug_final

        # stock inputs
        stock = attrs.pop("stock", None)
        wh_id = attrs.pop("warehouse_id", None)
        allocations = self.initial_data.get("stock_allocations")

        if allocations and (stock is not None or wh_id is not None):
            raise serializers.ValidationError(
                {"stock_allocations": "Use either stock_allocations OR (stock + warehouse_id), not both."}
            )

        if allocations:
            cleaned: List[Dict[str, int]] = []
            for item in allocations:
                wid = int(item.get("warehouse"))
                qty = int(item.get("quantity"))
                if not Warehouse.objects.filter(id=wid).exists():
                    raise serializers.ValidationError({"stock_allocations": f"Warehouse {wid} not found."})
                cleaned.append({"warehouse": wid, "quantity": qty})
            attrs["_allocations"] = cleaned
        elif stock is not None:
            if wh_id is None:
                raise serializers.ValidationError({"warehouse_id": "Required when providing 'stock'."})
            if not Warehouse.objects.filter(id=wh_id).exists():
                raise serializers.ValidationError({"warehouse_id": f"Warehouse {wh_id} not found."})
            attrs["_allocations"] = [{"warehouse": int(wh_id), "quantity": int(stock)}]
        else:
            attrs["_allocations"] = []

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        acting_owner_id = validated_data.pop("_acting_owner_id")
        allocations = validated_data.pop("_allocations", [])

        vendor_field = get_vendor_field(Product)  # e.g. 'owner' or 'vendor'
        product = Product.objects.create(**{f"{vendor_field}_id": acting_owner_id}, **validated_data)

        for alloc in allocations:
            ProductStock.objects.update_or_create(
                product=product, warehouse_id=alloc["warehouse"],
                defaults={"quantity": alloc["quantity"]},
            )
        return product


# -----------------------
# Vendor staff management
# -----------------------
class VendorStaffCreateSerializer(serializers.Serializer):
    owner_id = serializers.IntegerField(required=False)
    staff_id = serializers.IntegerField(required=True)
    role = serializers.ChoiceField(choices=[("staff", "Staff"), ("owner", "Owner")], default="staff")

    def to_internal_value(self, data):
        data = dict(data)
        if "owner" in data and "owner_id" not in data:
            data["owner_id"] = data["owner"]
        if "staff" in data and "staff_id" not in data:
            data["staff_id"] = data["staff"]
        return super().to_internal_value(data)

    def validate(self, attrs):
        req = self.context.get("request")
        owner_id = attrs.get("owner_id") or (req.user.id if req and req.user.is_authenticated else None)
        staff_id = attrs["staff_id"]
        if owner_id == staff_id:
            raise serializers.ValidationError({"staff_id": "Owner cannot equal staff."})
        return attrs

    def create(self, attrs):
        req = self.context.get("request")
        owner = User.objects.get(pk=attrs.get("owner_id") or req.user.id)
        staff = User.objects.get(pk=attrs["staff_id"])
        return services.add_or_activate_staff(owner, staff, attrs.get("role", "staff"))


class VendorStaffOutSerializer(serializers.ModelSerializer):
    owner_id = serializers.IntegerField(read_only=True)
    staff_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = VendorStaff
        fields = ["id", "owner_id", "staff_id", "role", "is_active", "created_at"]
        read_only_fields = fields


class VendorStaffInviteSerializer(serializers.Serializer):
    owner_id = serializers.IntegerField(required=False, allow_null=True)
    staff_id = serializers.IntegerField(required=False)
    staff_email = serializers.EmailField(required=False)

    def validate(self, attrs):
        request = self.context["request"]

        # Resolve owner id (fallback to current user, or require explicit if multiple)
        try:
            owner_id = resolve_vendor_owner_for(
                request.user,
                attrs.get("owner_id"),
                require_explicit_if_multiple=True,
            )
        except ValueError as e:
            raise serializers.ValidationError({"owner_id": str(e)})

        # Resolve staff by id or email
        staff = None
        if attrs.get("staff_id") is not None:
            staff = User.objects.filter(pk=attrs["staff_id"]).first()
            if not staff:
                raise serializers.ValidationError({"staff_id": "User not found."})
        elif attrs.get("staff_email"):
            email = attrs["staff_email"].strip().lower()
            staff = User.objects.filter(email__iexact=email).first()
            if not staff:
                raise serializers.ValidationError({"staff_email": "No user with that email."})
        else:
            raise serializers.ValidationError({"staff": "Provide staff_id or staff_email."})

        if staff.id == owner_id:
            raise serializers.ValidationError({"owner_id": "You cannot invite yourself."})

        attrs["owner_id"] = owner_id
        attrs["staff"] = staff
        return attrs


class VendorStaffRemoveSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()
    owner_id = serializers.IntegerField(required=False)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            owner_id = resolve_vendor_owner_for(request.user, self.validated_data.get("owner_id"))
        except ValueError as e:
            raise serializers.ValidationError({"owner_id": str(e)})

        try:
            membership = VendorStaff.objects.get(owner_id=owner_id, staff_id=self.validated_data["staff_id"])
        except VendorStaff.DoesNotExist:
            return {"ok": True}

        # wrapper provided in users/services.py
        services.deactivate_vendor_staff(membership)
        return {"ok": True}


# -----------------------
# Vendor Application (KYC)
# -----------------------
KRA_PIN_RE = re.compile(r"^[A-Z]\d{9}[A-Z]$", re.I)


class VendorApplicationCreateSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(max_length=120, allow_blank=False, required=True)
    phone = serializers.CharField(max_length=32, allow_blank=False, required=True)
    kra_pin = serializers.CharField(max_length=32, allow_blank=False, required=True)
    national_id = serializers.CharField(max_length=32, allow_blank=False, required=True)
    document = serializers.FileField(required=True)
    note = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = VendorApplication
        fields = [
            "company_name",
            "phone",
            "kra_pin",
            "national_id",
            "document",
            "note",
        ]

    def validate_company_name(self, v):
        v = (v or "").strip()
        if not v:
            raise serializers.ValidationError("Company name is required.")
        return v

    def validate_kra_pin(self, v):
        v = (v or "").strip().upper()
        if not KRA_PIN_RE.match(v):
            raise serializers.ValidationError("KRA PIN must look like A123456789B.")
        return v

    def validate_phone(self, v):
        v = (v or "").strip()
        if len(v) < 7:
            raise serializers.ValidationError("Phone number looks too short.")
        return v

    def validate_document(self, f):
        if getattr(f, "size", 0) > 5 * 1024 * 1024:
            raise serializers.ValidationError("File too large (max 5MB).")
        return f

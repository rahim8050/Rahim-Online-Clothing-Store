# apis/serializers.py
from django.apps import apps
from django.db import transaction
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

# Your models
from product_app.models import Product, ProductStock, Warehouse
from orders.models import OrderItem
from users.models import VendorStaff, VendorApplication
from users.services import deactivate_vendor_staff
from users.constants import VENDOR_STAFF
from users.utils import resolve_vendor_owner_for

User = get_user_model()

# ----------------------------------------
# Helpers
# ----------------------------------------
# ----------------------------------------
# Order / Product basic serializers
# ----------------------------------------
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "order", "product", "price", "quantity", "delivery_status"]


class ProductSerializer(serializers.ModelSerializer):
    # If related_name differs, adjust "order_items" -> your related_name or "orderitem_set"
    order_items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "price", "available", "order_items"]


class ProductListSerializer(serializers.ModelSerializer):
    owned_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "price", "available", "slug", "owned_by_me"]

    def get_owned_by_me(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        for name in ("owner", "vendor", "seller", "created_by", "user"):
            try:
                obj._meta.get_field(name)
                return getattr(obj, f"{name}_id", None) == user.id
            except Exception:
                continue
        return False


# ----------------------------------------
# Optional Delivery support (model may not exist)
# ----------------------------------------
class _EmptySerializer(serializers.Serializer):
    pass

try:
    DeliveryModel = apps.get_model("orders", "Delivery")  # may raise LookupError
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
    # Build choices dynamically if Delivery model exists; otherwise behave like CharField
    status = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        if DeliveryModel is not None:
            # Prefer model field choices if present
            try:
                field = DeliveryModel._meta.get_field("status")
                if getattr(field, "choices", None):
                    choices = [c[0] for c in field.choices]
            except Exception:
                pass
            # Or enum-style `Status.choices`
            if not choices and hasattr(DeliveryModel, "Status") and getattr(DeliveryModel.Status, "choices", None):
                choices = [c[0] for c in DeliveryModel.Status.choices]
        if choices:
            self.fields["status"] = serializers.ChoiceField(choices=choices)


# ----------------------------------------
# Vendor product creation (single, consolidated version)
# Supports:
#   - owner_id (acts for an owner if vendor-staff)
#   - optional sku/stock/warehouse_id OR stock_allocations = [{warehouse, quantity}, ...]
# ----------------------------------------
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
    def _normalize_slug(self, provided_slug, provided_sku, provided_name):
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
        slug_in = attrs.get("slug", "").strip()
        sku_in = attrs.pop("sku", "").strip()
        name_in = attrs.get("name", "").strip()
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
            cleaned = []
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
        product = Product.objects.create(owner_id=acting_owner_id, **validated_data)
        for alloc in allocations:
            ProductStock.objects.update_or_create(
                product=product, warehouse_id=alloc["warehouse"],
                defaults={"quantity": alloc["quantity"]},
            )
        return product


# ----------------------------------------
# Vendor staff management
# ----------------------------------------
class VendorStaffInviteSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()
    owner_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        request = self.context["request"]
        try:
            owner_id = resolve_vendor_owner_for(request.user, attrs.get("owner_id"))
        except ValueError as e:
            raise serializers.ValidationError({"owner_id": str(e)})
        try:
            staff = User.objects.get(pk=attrs["staff_id"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"staff_id": "User not found."})
        attrs["owner_id"] = owner_id
        attrs["staff"] = staff
        return attrs

    def create(self, validated):
        owner_id = validated["owner_id"]
        staff = validated["staff"]
        vs, _ = VendorStaff.objects.update_or_create(
            owner_id=owner_id, staff=staff,
            defaults={"role": VendorStaff.Role.STAFF, "is_active": True},
        )
        Group.objects.get_or_create(name=VENDOR_STAFF)[0].user_set.add(staff)
        return vs


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
        deactivate_vendor_staff(membership)
        return {"ok": True}


# ----------------------------------------
# Vendor application (matches your JSON)
# JSON body:
# {
#   "business_name": "Rahim Traders",
#   "kra_pin": "A123456789B",
#   "contact_phone": "+254700000000",
#   "company_name": "rahims",
#   "contact_email": "owner@example.com"
# }
# ----------------------------------------
import re

class VendorApplySerializer(serializers.ModelSerializer):
    business_name = serializers.CharField()
    kra_pin = serializers.CharField()
    contact_phone = serializers.CharField()
    company_name = serializers.CharField()
    contact_email = serializers.EmailField()

    class Meta:
        model = VendorApplication
        fields = ["business_name", "kra_pin", "contact_phone", "company_name", "contact_email"]

    def validate_kra_pin(self, v):
        v = v.strip().upper()
        if not re.match(r"^[A-Z]\d{9}[A-Z]$", v):
            raise serializers.ValidationError("Invalid KRA PIN format (e.g. A123456789B).")
        return v

    def validate_contact_phone(self, v):
        s = v.replace(" ", "")
        if s.startswith("07") and len(s) == 10:
            s = "+254" + s[1:]
        if not re.match(r"^\+2547\d{8}$", s):
            raise serializers.ValidationError("Phone must be like +2547XXXXXXXX.")
        return s

    def create(self, validated):
        user = self.context["request"].user
        # Your VendorApplication should have fields named as above + user + status
        return VendorApplication.objects.create(user=user, status="pending", **validated)


# ----------------------------------------
# Product read-out with stocks (safe even if related_name differs)
# ----------------------------------------
class ProductOutSerializer(serializers.ModelSerializer):
    stocks = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "description", "price", "available",
            "category", "owner", "image", "created", "updated", "stocks"
        ]

    def get_stocks(self, obj):
        return list(
            ProductStock.objects.filter(product=obj).values("warehouse_id", "quantity")
        )

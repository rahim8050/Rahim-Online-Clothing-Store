from django.apps import apps
from rest_framework import serializers
from users.models import VendorStaff
from product_app.models import Product
from orders.models import OrderItem
from django.contrib.auth import get_user_model
from users.utils import resolve_vendor_owner_for
from users.models import VendorApplication
User = get_user_model()


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "order", "product", "price", "quantity", "delivery_status"]


class ProductSerializer(serializers.ModelSerializer):
    # If your FK on OrderItem uses related_name="order_items", this is fine.
    # If not, change `source` to the actual related name (e.g. "orderitem_set").
    order_items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "price", "available", "order_items"]


# ---- Optional Delivery serializer (won't explode if model is absent) ----
class EmptySerializer(serializers.Serializer):
    """Used when Delivery model doesn't exist."""
    pass

try:
    DeliveryModel = apps.get_model("orders", "Delivery")  # raises LookupError if absent
except LookupError:
    DeliveryModel = None

if DeliveryModel is not None:
    class DeliverySerializer(serializers.ModelSerializer):
        class Meta:
            model = DeliveryModel
            fields = "__all__"
else:
    # Keep a symbol so `from .serializers import DeliverySerializer` never fails.
    DeliverySerializer = EmptySerializer


class DeliveryAssignSerializer(serializers.Serializer):
    driver_id = serializers.IntegerField()


class DeliveryUnassignSerializer(serializers.Serializer):
    pass


class DeliveryStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[c[0] for c in DeliveryModel.Status.choices] if DeliveryModel else [])




class VendorProductCreateSerializer(serializers.ModelSerializer):
    # Optional: staff can choose which owner if they belong to multiple
    owner_id = serializers.IntegerField(required=False, write_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "price", "available", "owner_id"]  # include other fields your Product has (image, category, etc.)
        read_only_fields = ["id"]

    def create(self, validated):
        request = self.context["request"]
        owner_id = validated.pop("owner_id", None)
        try:
            vendor_owner_id = resolve_vendor_owner_for(request.user, owner_id)
        except ValueError as e:
            raise serializers.ValidationError({"owner_id": str(e)})

        # Your Product must have vendor/user/owner FK field. Adjust to your actual field.
        # If your field is named 'vendor':
        validated["vendor_id"] = vendor_owner_id
        return Product.objects.create(**validated)
class VendorStaffInviteSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()
    owner_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        request = self.context["request"]
        owner_id = attrs.get("owner_id") or resolve_vendor_owner_for(request.user)  # infer owner if unique
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
        # ensure group
        from django.contrib.auth.models import Group
        Group.objects.get_or_create(name="Vendor Staff")[0].user_set.add(staff)
        return vs


class VendorStaffRemoveSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()
    owner_id = serializers.IntegerField(required=False)

    def save(self, **kwargs):
        request = self.context["request"]
        owner_id = self.validated_data.get("owner_id") or resolve_vendor_owner_for(request.user)
        VendorStaff.objects.filter(owner_id=owner_id, staff_id=self.validated_data["staff_id"]).update(is_active=False)
        return {"ok": True}
    
    
class VendorApplySerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorApplication
        fields = ["company_name", "phone", "note"]

    def create(self, validated):
        user = self.context["request"].user
        return VendorApplication.objects.create(user=user, **validated)    
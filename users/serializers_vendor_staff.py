from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from .constants import VENDOR_STAFF
from .models import VendorStaff
from .services import deactivate_vendor_staff
from .utils import resolve_vendor_owner_for

User = get_user_model()


class VendorStaffReadSerializer(serializers.ModelSerializer):
    staff_email = serializers.EmailField(source="staff.email", read_only=True)
    staff_name = serializers.CharField(source="staff.get_full_name", read_only=True)

    class Meta:
        model = VendorStaff
        fields = [
            "id",
            "owner",
            "staff",
            "role",
            "is_active",
            "created_at",
            "staff_email",
            "staff_name",
        ]
        read_only_fields = fields


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

        if request.user.pk == staff.pk:
            raise serializers.ValidationError(
                {"staff_id": "Owner cannot invite themselves as staff."}
            )

        attrs["owner_id"] = owner_id
        attrs["staff"] = staff
        return attrs

    def create(self, validated_data):
        owner_id = validated_data["owner_id"]
        staff = validated_data["staff"]
        membership, _ = VendorStaff.objects.update_or_create(
            owner_id=owner_id,
            staff=staff,
            defaults={"role": VendorStaff.Role.STAFF, "is_active": True},
        )
        Group.objects.get_or_create(name=VENDOR_STAFF)[0].user_set.add(staff)
        return membership


class VendorStaffRemoveSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()
    owner_id = serializers.IntegerField(required=False)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            owner_id = resolve_vendor_owner_for(
                request.user, self.validated_data.get("owner_id")
            )
        except ValueError as e:
            raise serializers.ValidationError({"owner_id": str(e)})

        try:
            membership = VendorStaff.objects.get(
                owner_id=owner_id, staff_id=self.validated_data["staff_id"]
            )
        except VendorStaff.DoesNotExist:
            return {"ok": True}

        deactivate_vendor_staff(membership)
        return {"ok": True}


class VendorStaffToggleSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()
    is_active = serializers.BooleanField()
    owner_id = serializers.IntegerField(required=False)

    def save(self, **kwargs):
        request = self.context["request"]
        try:
            owner_id = resolve_vendor_owner_for(
                request.user, self.validated_data.get("owner_id")
            )
        except ValueError as e:
            raise serializers.ValidationError({"owner_id": str(e)})

        try:
            membership = VendorStaff.objects.get(
                owner_id=owner_id, staff_id=self.validated_data["staff_id"]
            )
        except VendorStaff.DoesNotExist:
            raise serializers.ValidationError({"staff_id": "Membership not found."})

        if self.validated_data["is_active"]:
            membership.is_active = True
            membership.save(update_fields=["is_active"])
            Group.objects.get_or_create(name=VENDOR_STAFF)[0].user_set.add(
                membership.staff
            )
        else:
            deactivate_vendor_staff(membership)

        return membership

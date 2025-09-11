from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import VendorMember, VendorOrg, VendorOrgAuditLog
from .services import has_min_role


class OrgSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    slug = serializers.SlugField(required=False, allow_blank=True)
    kra_pin = serializers.CharField(required=False, allow_blank=True)
    tax_status = serializers.ChoiceField(choices=VendorOrg.TaxStatus.choices, required=False)

    class Meta:
        model = VendorOrg
        fields = [
            "id",
            "name",
            "slug",
            "owner",
            "is_active",
            "kra_pin",
            "tax_status",
            "tax_registered_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def _can_see_sensitive(self, user, org: VendorOrg) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True
        try:
            return has_min_role(user, org, "MANAGER")
        except Exception:
            return False

    def to_representation(self, instance: VendorOrg):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not self._can_see_sensitive(user, instance):
            data.pop("kra_pin", None)
        return data

    def validate_kra_pin(self, v: str):
        v = (v or "").strip().upper()
        if not v:
            return v
        import re
        if not re.match(r"^[A-Z]{1}[0-9]{9}[A-Z]{1}$", v):
            raise serializers.ValidationError("KRA PIN must look like A123456789B.")
        return v

    def update(self, instance: VendorOrg, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        # Enforce role for sensitive fields
        sensitive = {}
        for f in ("kra_pin", "tax_status", "tax_registered_at"):
            if f in validated_data:
                sensitive[f] = validated_data[f]
        if sensitive and not self._can_see_sensitive(user, instance):
            raise serializers.ValidationError({"detail": "Not allowed to modify tax fields."})

        # Track old values for audit
        old_vals = {k: getattr(instance, k, None) for k in sensitive.keys()}
        obj = super().update(instance, validated_data)
        # Validate at model level for KRA PIN format & normalize
        obj.full_clean()
        obj.save()

        # Audit changes
        for field, new_val in sensitive.items():
            old_val = old_vals.get(field)
            if str(old_val) != str(new_val):
                try:
                    VendorOrgAuditLog.objects.create(
                        actor=user if getattr(user, "is_authenticated", False) else None,
                        org=obj,
                        field=field,
                        old_value=str(old_val or ""),
                        new_value=str(new_val or ""),
                    )
                except Exception:
                    pass
        return obj


class MemberSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()

    class Meta:
        model = VendorMember
        fields = [
            "id",
            "org",
            "user",
            "role",
            "is_active",
            "created_at",
            "user_email",
            "user_username",
        ]
        read_only_fields = ["id", "created_at", "org"]

    def get_user_email(self, obj):
        return getattr(obj.user, "email", None)

    def get_user_username(self, obj):
        return getattr(obj.user, "username", None)


class InviteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    email = serializers.EmailField(required=False)
    role = serializers.ChoiceField(
        choices=[("STAFF", "Staff"), ("MANAGER", "Manager"), ("OWNER", "Owner")],
        default="STAFF",
    )

    def validate(self, attrs):
        User = get_user_model()
        user = None
        if attrs.get("user_id"):
            user = User.objects.filter(pk=attrs["user_id"]).first()
            if not user:
                raise serializers.ValidationError({"user_id": "User not found"})
        elif attrs.get("email"):
            user = User.objects.filter(email__iexact=attrs["email"]).first()
            if not user:
                raise serializers.ValidationError({"email": "User not found"})
        else:
            raise serializers.ValidationError({"user": "Provide user_id or email"})
        attrs["_user"] = user
        attrs["role"] = (attrs.get("role") or "STAFF").upper()
        return attrs

    def create(self, validated_data):
        org: VendorOrg = self.context["org"]
        user = validated_data["_user"]
        role = validated_data["role"]
        return org.add_member(user, role)

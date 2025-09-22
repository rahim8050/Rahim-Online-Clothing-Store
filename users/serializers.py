from rest_framework import serializers

from .models import VendorApplication


class VendorApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorApplication
        fields = ["company_name", "phone", "note", "kra_pin", "national_id", "document"]


class VendorApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorApplication
        fields = "__all__"
        read_only_fields = ["status", "decided_by", "decided_at", "user", "created_at"]

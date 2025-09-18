from __future__ import annotations

from rest_framework import serializers

from .models import Invoice, InvoiceLine


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["id", "sku", "name", "qty", "unit_price", "tax_rate", "line_total", "tax_total"]
        read_only_fields = ["id", "line_total", "tax_total"]


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "org",
            "order",
            "buyer_name",
            "buyer_pin",
            "subtotal",
            "tax_amount",
            "total",
            "currency",
            "status",
            "irn",
            "issued_at",
            "updated_at",
            "submitted_at",
            "accepted_at",
            "rejected_at",
            "last_error",
            "lines",
        ]
        read_only_fields = [
            "id",
            "subtotal",
            "tax_amount",
            "total",
            "status",
            "irn",
            "issued_at",
            "updated_at",
            "submitted_at",
            "accepted_at",
            "rejected_at",
            "last_error",
            "lines",
        ]


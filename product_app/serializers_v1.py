from rest_framework import serializers

from .models import Category, Product


class CategoryV1Serializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductV1Serializer(serializers.ModelSerializer):
    # Nested read-only category
    category = CategoryV1Serializer(read_only=True)
    # Write-only helper
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price",
            "available",
            "created",
            "updated",
            "product_version",
            "image",
            "category",
            "category_id",
            "owner",
        ]
        read_only_fields = ["id", "created", "updated", "product_version", "owner", "category"]

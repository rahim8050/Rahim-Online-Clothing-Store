from rest_framework import permissions, viewsets

from .models import Category, Product
from .serializers_v1 import CategoryV1Serializer, ProductV1Serializer


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser))


class CategoryV1ViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategoryV1Serializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsStaffOrReadOnly]
    filterset_fields = ["slug", "name"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name"]


class ProductV1ViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category").all().order_by("-created")
    serializer_class = ProductV1Serializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsStaffOrReadOnly]
    filterset_fields = ["category__id", "available"]
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["created", "price", "name"]

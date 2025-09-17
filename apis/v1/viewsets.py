from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from product_app.models import Category, Product, Warehouse, ProductStock
from orders.models import Order, OrderItem

from .serializers import (
    CategorySerializer,
    ProductSerializer,
    WarehouseSerializer,
    ProductStockSerializer,
    OrderSerializer,
    OrderItemSerializer,
)


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow safe methods to everyone; write only to the Product owner or staff."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if getattr(u, "is_staff", False) or getattr(u, "is_superuser", False):
            return True
        owner_id = getattr(obj, "owner_id", None)
        return owner_id and owner_id == u.id


# --------------- Catalog ----------------
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("category").all().order_by("-created")
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def perform_create(self, serializer):
        u = self.request.user
        if not (u and u.is_authenticated):
            raise PermissionDenied("Authentication required to create products.")
        serializer.save(owner=u)

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        available = self.request.query_params.get("available")
        if available in {"1", "true", "True"}:
            qs = qs.filter(available=True)
        return qs


class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True).order_by("name")
    serializer_class = WarehouseSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ProductStockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProductStock.objects.select_related("product", "warehouse").all()
    serializer_class = ProductStockSerializer
    permission_classes = [permissions.IsAuthenticated]


# --------------- Orders -----------------
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        base = Order.objects.all().order_by("-created_at")
        if u and (u.is_staff or u.is_superuser):
            return base
        if u and u.is_authenticated:
            return base.filter(user=u)
        # no anonymous order listing
        return base.none()


class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        qs = (OrderItem.objects
              .select_related("order", "product", "warehouse")
              .order_by("-id"))
        if u and (u.is_staff or u.is_superuser):
            return qs
        if u and u.is_authenticated:
            return qs.filter(order__user=u)
        return qs.none()

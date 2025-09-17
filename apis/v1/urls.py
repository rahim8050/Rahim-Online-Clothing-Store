from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .viewsets import (
    CategoryViewSet,
    ProductViewSet,
    WarehouseViewSet,
    ProductStockViewSet,
    OrderViewSet,
    OrderItemViewSet,
)

# Reuse existing WhoAmI from apis.views for consistency
try:
    from apis.views import WhoAmI  # type: ignore
except Exception:  # pragma: no cover - guard if module moves
    WhoAmI = None

router = DefaultRouter()

# Catalog
router.register(r"catalog/categories", CategoryViewSet, basename="v1-categories")
router.register(r"catalog/products", ProductViewSet, basename="v1-products")

# Inventory
router.register(r"inventory/warehouses", WarehouseViewSet, basename="v1-warehouses")
router.register(r"inventory/stocks", ProductStockViewSet, basename="v1-stocks")

# Orders
router.register(r"orders/orders", OrderViewSet, basename="v1-orders")
router.register(r"orders/items", OrderItemViewSet, basename="v1-order-items")


urlpatterns = [
    # Auth
    path("auth/token/", TokenObtainPairView.as_view(), name="v1-token-obtain"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="v1-token-refresh"),
]

if WhoAmI is not None:
    urlpatterns += [path("auth/me/", WhoAmI.as_view(), name="v1-whoami")]

urlpatterns += router.urls


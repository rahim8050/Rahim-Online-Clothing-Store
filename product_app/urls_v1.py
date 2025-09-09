from rest_framework.routers import DefaultRouter
from .views_v1 import CategoryV1ViewSet, ProductV1ViewSet

router = DefaultRouter()
router.register(r"categories", CategoryV1ViewSet, basename="v1-categories")
router.register(r"products", ProductV1ViewSet, basename="v1-products")

urlpatterns = router.urls


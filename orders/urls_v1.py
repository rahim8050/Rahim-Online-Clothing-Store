from rest_framework.routers import DefaultRouter

from .views_v1 import OrderV1ViewSet

router = DefaultRouter()
router.register(r"orders", OrderV1ViewSet, basename="v1-orders")

urlpatterns = router.urls

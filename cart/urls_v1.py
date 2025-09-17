from rest_framework.routers import DefaultRouter
from .views_v1 import CartV1ViewSet

router = DefaultRouter()
router.register(r"carts", CartV1ViewSet, basename="v1-carts")

urlpatterns = router.urls


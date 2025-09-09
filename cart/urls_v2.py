from rest_framework.routers import DefaultRouter
from .views_v2 import CartViewSet

router = DefaultRouter()
router.register(r"carts", CartViewSet, basename="cart-v2")

urlpatterns = router.urls


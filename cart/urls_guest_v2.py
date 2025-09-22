from rest_framework.routers import DefaultRouter

from .views_guest_v2 import GuestCartViewSet

router = DefaultRouter()
router.register("carts", GuestCartViewSet, basename="guest-cart")

urlpatterns = router.urls

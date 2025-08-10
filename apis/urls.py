from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import VendorProductsAPI, DriverDeliveriesAPI

urlpatterns = [
    path('vendor/products/', VendorProductsAPI.as_view(), name='vendor-products'),
    path('driver/deliveries/', DriverDeliveriesAPI.as_view(), name='driver-deliveries'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

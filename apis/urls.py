from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    VendorProductsAPI,
    DriverDeliveriesAPI,
    DeliveryAssignAPI,
    DeliveryUnassignAPI,
    DeliveryAcceptAPI,
    DeliveryStatusAPI,
)

urlpatterns = [
    path('vendor/products/', VendorProductsAPI.as_view(), name='vendor-products'),
    path('driver/deliveries/', DriverDeliveriesAPI.as_view(), name='driver-deliveries'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

urlpatterns += [
    path("deliveries/<int:pk>/assign/",   DeliveryAssignAPI.as_view(),   name="delivery-assign"),
    path("deliveries/<int:pk>/unassign/", DeliveryUnassignAPI.as_view(), name="delivery-unassign"),
    path("deliveries/<int:pk>/accept/",   DeliveryAcceptAPI.as_view(),   name="delivery-accept"),
    path("deliveries/<int:pk>/status/",   DeliveryStatusAPI.as_view(),   name="delivery-status"),
]

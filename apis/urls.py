from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apis.views import (
    # general
    WhoAmI,
    ShopableProductsAPI,
    VendorProductsAPI,
    VendorProductCreateAPI,
    DriverLocationAPI,
    DriverDeliveriesAPI,
    DeliveryAssignAPI,
    DeliveryUnassignAPI,
    DeliveryAcceptAPI,
    DeliveryStatusAPI,
    VendorApplyAPI,

    # vendor staff (all from apis.views)
    VendorStaffListCreateView,
    VendorStaffInviteAPI,
    VendorStaffAcceptAPI,
    VendorStaffRemoveAPI,
    # VendorStaffToggleActiveAPI,  # uncomment if you implemented it in apis.views
)

urlpatterns = [
    # Auth
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/whoami/", WhoAmI.as_view(), name="whoami"),

    # Vendor products
    path("vendor/products/", VendorProductsAPI.as_view(), name="vendor-products"),
    path("vendor/products/create/", VendorProductCreateAPI.as_view(), name="vendor-product-create"),
    path("vendor/shopable-products/", ShopableProductsAPI.as_view(), name="shopable-products"),

    # Driver
    path("driver/deliveries/", DriverDeliveriesAPI.as_view(), name="driver-deliveries"),
    path("driver/location/", DriverLocationAPI.as_view(), name="driver-location"),

    # Deliveries management
    path("deliveries/<int:pk>/assign/", DeliveryAssignAPI.as_view(), name="delivery-assign"),
    path("deliveries/<int:pk>/unassign/", DeliveryUnassignAPI.as_view(), name="delivery-unassign"),
    path("deliveries/<int:pk>/accept/", DeliveryAcceptAPI.as_view(), name="delivery-accept"),
    path("deliveries/<int:pk>/status/", DeliveryStatusAPI.as_view(), name="delivery-status"),

    # Vendor staff (consistent module)
    path("vendor/staff/", VendorStaffListCreateView.as_view(), name="vendor-staff-list"),
    path("vendor/staff/invite/", VendorStaffInviteAPI.as_view(), name="vendor-staff-invite"),
    path("vendor/staff/accept/<str:token>/", VendorStaffAcceptAPI.as_view(), name="vendor-staff-accept"),
    path("vendor/staff/<int:staff_id>/remove/", VendorStaffRemoveAPI.as_view(), name="vendor-staff-remove"),
    # path("vendor/staff/<int:staff_id>/toggle/", VendorStaffToggleActiveAPI.as_view(), name="vendor-staff-toggle"),
]

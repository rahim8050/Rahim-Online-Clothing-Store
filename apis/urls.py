from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    VendorProductsAPI,
    DriverDeliveriesAPI,
    DeliveryAssignAPI,
    DeliveryUnassignAPI,
    DeliveryAcceptAPI,
    DeliveryStatusAPI,
    VendorProductCreateAPI,
    VendorApplyAPI,
    ShopableProductsAPI,
    DriverLocationAPI,
)
from users.views_vendor_staff import (
    VendorStaffListAPI,
    VendorStaffInviteAPI,
    VendorStaffRemoveAPI,
    VendorStaffToggleActiveAPI,
)

urlpatterns = [
    path("vendor/products/", VendorProductsAPI.as_view(), name="vendor-products"),
    path(
        "vendor/shopable-products/",
        ShopableProductsAPI.as_view(),
        name="shopable-products",
    ),
    path("driver/deliveries/", DriverDeliveriesAPI.as_view(), name="driver-deliveries"),
    path("driver/location/", DriverLocationAPI.as_view(), name="driver-location"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Delivery management endpoints
    path(
        "deliveries/<int:pk>/assign/",
        DeliveryAssignAPI.as_view(),
        name="delivery-assign",
    ),
    path(
        "deliveries/<int:pk>/unassign/",
        DeliveryUnassignAPI.as_view(),
        name="delivery-unassign",
    ),
    path(
        "deliveries/<int:pk>/accept/",
        DeliveryAcceptAPI.as_view(),
        name="delivery-accept",
    ),
    path(
        "deliveries/<int:pk>/status/",
        DeliveryStatusAPI.as_view(),
        name="delivery-status",
    ),
    path(
        "vendor/products/create/",
        VendorProductCreateAPI.as_view(),
        name="vendor-product-create",
    ),
    path("vendor/apply/", VendorApplyAPI.as_view(), name="vendor-apply"),
    # Vendor staff management
    path("vendor/staff/", VendorStaffListAPI.as_view(), name="vendor-staff-list"),
    path(
        "vendor/staff/invite/",
        VendorStaffInviteAPI.as_view(),
        name="vendor-staff-invite",
    ),
    path(
        "vendor/staff/remove/",
        VendorStaffRemoveAPI.as_view(),
        name="vendor-staff-remove",
    ),
    path(
        "vendor/staff/<int:staff_id>/",
        VendorStaffRemoveAPI.as_view(),
        name="vendor-staff-remove-id",
    ),
    path(
        "vendor/staff/toggle/",
        VendorStaffToggleActiveAPI.as_view(),
        name="vendor-staff-toggle",
    ),
]

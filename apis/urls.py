# apis/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apis.views import (  # Driver + deliveries; Vendor application; Vendor utilities; Vendor staff; General
    DeliveryAcceptAPI,
    DeliveryAssignAPI,
    DeliveryStatusAPI,
    DeliveryUnassignAPI,
    DriverDeliveriesAPI,
    DriverLocationAPI,
    ShopableProductsAPI,
    VendorApplyAPI,
    VendorDeliveriesAPI,
    VendorOwnersAPI,
    VendorProductCreateAPI,
    VendorProductsAPI,
    VendorProductsExportCSV,
    VendorProductsImportCSV,
    VendorStaffAcceptAPI,
    VendorStaffDeactivateAPI,
    VendorStaffInviteAPI,
    VendorStaffListCreateView,
    VendorStaffRemoveAPI,
    WhoAmI,
)
from apis.views_vendor import VendorKPIAPI
from orders.api_driver import DeliveryViewSet

app_name = "apis"

router = DefaultRouter()
router.register(r"deliveries", DeliveryViewSet, basename="driver-deliveries-v2")

urlpatterns = [
    # Auth
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/whoami/", WhoAmI.as_view(), name="whoami"),
    # Vendor products
    path("vendor/products/", VendorProductsAPI.as_view(), name="vendor-products"),
    path(
        "vendor/products/create/",
        VendorProductCreateAPI.as_view(),
        name="vendor-product-create",
    ),
    path(
        "vendor/shopable-products/",
        ShopableProductsAPI.as_view(),
        name="shopable-products",
    ),
    # Vendor application / KPIs
    path("vendor/apply/", VendorApplyAPI.as_view(), name="vendor-apply"),
    path("vendor/kpis/", VendorKPIAPI.as_view(), name="vendor-kpis"),
    # Driver
    path("driver/deliveries/", DriverDeliveriesAPI.as_view(), name="driver-deliveries"),
    path("driver/location/", DriverLocationAPI.as_view(), name="driver-location"),
    # Deliveries management
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
    # Vendor staff
    path(
        "vendor/staff/", VendorStaffListCreateView.as_view(), name="vendor-staff-list"
    ),
    path(
        "vendor/staff/invite/",
        VendorStaffInviteAPI.as_view(),
        name="vendor-staff-invite",
    ),
    path(
        "vendor/staff/accept/<str:token>/",
        VendorStaffAcceptAPI.as_view(),
        name="vendor-staff-accept",
    ),
    path(
        "vendor/staff/<int:staff_id>/remove/",
        VendorStaffRemoveAPI.as_view(),
        name="vendor-staff-remove",
    ),
    path(
        "vendor/staff/<int:staff_id>/deactivate/",
        VendorStaffDeactivateAPI.as_view(),
        name="vendor-staff-deactivate",
    ),
    # Vendor deliveries & utilities
    path("vendor/deliveries/", VendorDeliveriesAPI.as_view(), name="vendor-deliveries"),
    path("vendor/owners/", VendorOwnersAPI.as_view(), name="vendor-owners"),
    path(
        "vendor/products/import-csv/",
        VendorProductsImportCSV.as_view(),
        name="vendor-products-import-csv",
    ),
    path(
        "vendor/products/export-csv/",
        VendorProductsExportCSV.as_view(),
        name="vendor-products-export-csv",
    ),
]

# DRF router endpoints
urlpatterns += router.urls

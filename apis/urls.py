from django.urls import path

from .views import VendorStaffInviteAPI, VendorStaffAcceptAPI

urlpatterns = [
    path("vendor/staff/invite/", VendorStaffInviteAPI.as_view(), name="vendor-staff-invite"),
    path(
        "vendor/staff/accept/<str:token>/",
        VendorStaffAcceptAPI.as_view(),
        name="vendor-staff-accept",
    ),
]

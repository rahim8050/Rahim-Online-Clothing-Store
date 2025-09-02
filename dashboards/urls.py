from django.urls import path
from .views import vendor_dashboard, vendor_live

urlpatterns = [
    path("vendor-dashboard/", vendor_dashboard, name="vendor-dashboard"),
    path("vendor/live/", vendor_live, name="vendor-live"),
]

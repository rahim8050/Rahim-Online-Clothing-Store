from django.urls import path
from .views import vendor_dashboard

urlpatterns = [
    path("vendor-dashboard/", vendor_dashboard, name="vendor-dashboard"),
]

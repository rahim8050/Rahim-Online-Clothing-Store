# dashboards/urls.py
from django.urls import path
from . import views

app_name = "dashboards"

urlpatterns = [
    path("vendor-dashboard/", views.vendor_dashboard, name="vendor-dashboard"),
    path("vendor/live/", views.vendor_live, name="vendor-live"),
]

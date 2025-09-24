from django.urls import include, path

from .views import PaymentReconcileAPI

urlpatterns = [
    path("reconcile/", PaymentReconcileAPI.as_view(), name="payments-reconcile"),
    path("", include("payments.urls_v1")),
]

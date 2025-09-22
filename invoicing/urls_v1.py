from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_export import DownloadCsvView, DownloadPdfView
from .views_v1 import InvoiceViewSet
from .views_webhook import EtimsWebhookView

router = DefaultRouter()
router.register(r"invoices", InvoiceViewSet, basename="invoices")

urlpatterns = [
    path("", include(router.urls)),
    path("etims/webhook", EtimsWebhookView.as_view(), name="etims-webhook"),
    path("invoices/<int:pk>/download.pdf", DownloadPdfView.as_view(), name="invoice-download-pdf"),
    path("invoices/<int:pk>/download.csv", DownloadCsvView.as_view(), name="invoice-download-csv"),
]

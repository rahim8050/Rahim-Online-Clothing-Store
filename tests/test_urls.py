from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from payments.views import MPesaWebhookView, PaystackWebhookView

urlpatterns = [
    path("apis/v1/schema/", SpectacularAPIView.as_view(), name="v1-schema"),
    path(
        "apis/v1/docs/",
        SpectacularSwaggerView.as_view(url_name="v1-schema"),
        name="v1-docs",
    ),
    path("apis/v1/vendor/", include("vendor_app.urls_v1")),
    path("apis/v1/invoicing/", include("invoicing.urls_v1")),
    path("webhook/paystack/", PaystackWebhookView.as_view(), name="webhook-paystack"),
    path("webhook/mpesa/", MPesaWebhookView.as_view(), name="webhook-mpesa"),
]

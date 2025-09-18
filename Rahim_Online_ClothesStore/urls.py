from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static

from users.views import debug_ws_push
from product_app import views as product_views
from users import views as user_views
from payments.views import (
    CheckoutView,
    StripeWebhookView,
    PaystackWebhookView,
    MPesaWebhookView,
)
from core.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),

    # Debug tools
    path("debug/ws-push/<int:delivery_id>/", debug_ws_push, name="debug-ws-push"),

    # App mounts
    path("utilities/", include("utilities.urls")),
    path("cart/", include("cart.urls")),
    path("orders/", include(("orders.urls", "orders"), namespace="orders")),

    # Home
    path("", product_views.product_list, name="index"),

    # --- Dashboards (single source: users.views) ---
    path("dashboard/", user_views.after_login, name="dashboard"),
    path("vendor-dashboard/", user_views.vendor_dashboard, name="vendor_dashboard"),
    path("driver-dashboard/", user_views.driver_dashboard, name="driver_dashboard"),

    # Auth + user routes (keep dashboards defined here; don't re-declare inside users.urls)
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("users.urls")),

    # Legacy API endpoints (existing, non-versioned)
    path("apis/", include("apis.urls")),
    path("api/assistant/", include("assistant.urls")),

    # New versioned API (DRF-only), per-app mounts
    path("apis/v1/schema/", SpectacularAPIView.as_view(), name="v1-schema"),
    path("apis/v1/docs/", SpectacularSwaggerView.as_view(url_name="v1-schema"), name="v1-docs"),

    # JWT endpoints (dev-friendly paths)
    path("apis/v1/auth/jwt/create/", TokenObtainPairView.as_view(), name="v1-jwt-create"),
    path("apis/v1/auth/jwt/refresh/", TokenRefreshView.as_view(), name="v1-jwt-refresh"),

    # Per-app v1 routers

    path("apis/v1/catalog/", include("product_app.urls_v1")),
    path("apis/v1/cart/", include("cart.urls_v1")),
    path("apis/v1/orders/", include("orders.urls_v1")),
    path("apis/v1/payments/", include("payments.urls_v1")),
    path("apis/v1/users/", include("users.urls_v1")),

    path('apis/v1/catalog/', include('product_app.urls_v1')),
    path('apis/v1/cart/', include('cart.urls_v1')),
    path('apis/v1/orders/', include('orders.urls_v1')),
    path('apis/v1/payments/', include('payments.urls_v1')),
    path('apis/v1/users/', include('users.urls_v1')),
    path('apis/v1/invoicing/', include('invoicing.urls_v1')),
    path('apis/v1/vendor/', include('vendor_app.urls_v1')),

    # v2 mounts (keep v1 intact)
    path("apis/v2/cart/", include("cart.urls_v2")),
    path("apis/v2/cart/guest/", include("cart.urls_guest_v2")),

    # Payments & webhooks
    path("payments/checkout/", CheckoutView.as_view(), name="payments_checkout"),
    path("webhook/stripe/", StripeWebhookView.as_view(), name="stripe_webhook"),
    path("webhook/paystack/", PaystackWebhookView.as_view(), name="paystack_webhook"),
    path("webhook/mpesa/", MPesaWebhookView.as_view(), name="mpesa_webhook"),


    # Health
    path("healthz", healthz, name="healthz"),  # keep path stable if already used
                                                 # (optionally change to "healthz/" and update probes)

    path('payments/checkout/', CheckoutView.as_view(), name='payments_checkout'),
    path('webhook/stripe/', StripeWebhookView.as_view(), name='stripe_webhook'),
    path('webhook/paystack/', PaystackWebhookView.as_view(), name='paystack_webhook'),
    path('webhook/mpesa/', MPesaWebhookView.as_view(), name='mpesa_webhook'),
    path('healthz', healthz, name='healthz'),
    path('readyz', __import__('core.views', fromlist=['readyz']).readyz, name='readyz'),


    # Product routes — keep AFTER dashboards so they don't shadow them
    path("products/search/", product_views.SearchProduct, name="product_search"),
    path(
        "products/",
        include(("product_app.urls", "product_app"), namespace="product_app"),
    ),
    path("category/<slug:category_slug>/", product_views.product_list, name="product_list_by_category"),

    # Profile
    path("accounts/profile/", product_views.profile, name="profile"),
]

# Static/media in dev (Render serves static in prod via WhiteNoise)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

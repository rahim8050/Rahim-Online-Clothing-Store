from django.contrib import admin
from django.urls import include, path
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
    path('admin/', admin.site.urls),
    path("debug/ws-push/<int:delivery_id>/", debug_ws_push, name="debug-ws-push"),
    path('utilities/', include('utilities.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include(('orders.urls', 'orders'), namespace='orders')),

    # Home
    path('', product_views.product_list, name='index'),

    # --- Dashboards (single source: users.views) ---
    path('dashboard/', user_views.after_login, name='dashboard'),
    path('vendor-dashboard/', user_views.vendor_dashboard, name='vendor_dashboard'),
    path('driver-dashboard/', user_views.driver_dashboard, name='driver_dashboard'),

    # Auth + user routes (DO NOT define dashboards inside users.urls)
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('users.urls')),

    # API prefix (align with your frontend: use /apis/... in fetch)
    path('apis/', include('apis.urls')),


    path('payments/checkout/', CheckoutView.as_view(), name='payments_checkout'),
    path('webhook/stripe/', StripeWebhookView.as_view(), name='stripe_webhook'),
    path('webhook/paystack/', PaystackWebhookView.as_view(), name='paystack_webhook'),
    path('webhook/mpesa/', MPesaWebhookView.as_view(), name='mpesa_webhook'),
    path('healthz', healthz, name='healthz'),

    # Product routes — keep AFTER dashboards so they don't shadow them
    path('products/search/', product_views.SearchProduct, name='product_search'),
    path('products/', include(('product_app.urls', 'product_app'), namespace='product_app')),
    path('category/<slug:category_slug>/', product_views.product_list, name='product_list_by_category'),

    path('accounts/profile/', product_views.profile, name='profile'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) \
  + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

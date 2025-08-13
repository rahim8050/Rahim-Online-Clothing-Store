from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from product_app import views as product_views
from users import views as user_views
from orders.views import paystack_webhook

urlpatterns = [
    path('admin/', admin.site.urls),

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

    path('webhook/paystack/', paystack_webhook, name='paystack_webhook'),

    # Product routes — keep AFTER dashboards so they don't shadow them
    path('products/search/', product_views.SearchProduct, name='product_search'),
    path('products/', include(('product_app.urls', 'product_app'), namespace='product_app')),
    path('category/<slug:category_slug>/', product_views.product_list, name='product_list_by_category'),

    path('accounts/profile/', product_views.profile, name='profile'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) \
  + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

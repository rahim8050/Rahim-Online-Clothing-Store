from django.urls import path

from .views import (
    product_list,
    SearchProduct,
    edit_product_view,
    start_listing_checkout_view,
    listing_webhook_view,
)

app_name = "product_app"

urlpatterns = [
    path('Product/search/', SearchProduct, name='SearchProduct'),
    path('<int:pk>/edit/', edit_product_view, name='edit_product'),
    path('<int:pk>/start-checkout/', start_listing_checkout_view, name='start_listing_checkout'),
    path('listing/webhook/', listing_webhook_view, name='listing_webhook'),
]

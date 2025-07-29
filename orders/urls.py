from django.urls import path

from .views import order_create, order_confirmation, get_location_info

from .views import (
    order_create,
    order_confirmation,
    stripe_checkout,
    paypal_payment,
    paypal_execute,
    payment_success,
    payment_cancel,
    Stripe_payment_success,
    stripe_webhook,
)


app_name = "orders"

urlpatterns = [
    path('create', order_create, name="order_create"),
    path("confirmation/<int:order_id>", order_confirmation, name="order_confirmation"),
    # Reverse geocode API
    path('api/reverse-geocode/', get_location_info, name='reverse_geocode'),
    # Stripe payment urls
    path('stripe/<int:order_id>/', stripe_checkout, name='stripe_checkout'),
    path("success/<int:order_id>/", Stripe_payment_success, name="payment_success"),
    path("webhook/stripe/", stripe_webhook, name="stripe-webhook"),
    # paypal payment urls
    path('paypal/<int:order_id>/', paypal_payment, name='paypal_payment'),
    path('paypal/execute/<int:order_id>/', paypal_execute, name='paypal_execute'),
    path('payment/success/<int:order_id>/', payment_success, name='payment_success'),
    path('payment/cancel/<int:order_id>/', payment_cancel, name='payment_cancel'),

]
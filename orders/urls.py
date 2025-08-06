from django.urls import path

from .views import order_create, order_confirmation, get_location_info, save_location

from .views import (
    order_create,
    order_confirmation,
    stripe_checkout,
    paystack_checkout,
    paypal_checkout,
    paypal_execute,
    paypal_payment,
    payment_success,
    payment_cancel,
    Stripe_payment_success,
    stripe_webhook,
    paystack_webhook,
    paypal_webhook,
    paystack_payment_confirm,
)


app_name = "orders"

urlpatterns = [
    path('create', order_create, name="order_create"),
    path("confirmation/<int:order_id>", order_confirmation, name="order_confirmation"),
    # Reverse geocode API
    path('api/reverse-geocode/', get_location_info, name='reverse_geocode'),
    # Stripe payment urls (not linked from UI)
    path('stripe/<int:order_id>/', stripe_checkout, name='stripe_checkout'),
    path("success/<int:order_id>/", Stripe_payment_success, name="payment_success"),
    path("webhook/stripe/", stripe_webhook, name="stripe-webhook"),
    # Paystack payment urls
    path('paystack/<int:order_id>/', paystack_checkout, name='paystack_checkout'),

    path('paystack/confirm/', paystack_payment_confirm, name='paystack_payment_confirm'),
    # ✅ New - maps directly to /webhook/paystack/

    path('orders/paystack/confirm/', paystack_payment_confirm, name='paystack_payment_confirm'),
    #  New - maps directly to /webhook/paystack/

    path("paystack/", paystack_webhook, name="paystack_webhook"),
    # PayPal payment urls
    path('paypal/<int:order_id>/', paypal_checkout, name='paypal_checkout'),
    path('paypal/execute/<int:order_id>/', paypal_execute, name='paypal_execute'),

    path('webhook/paypal/', paypal_webhook, name='paypal_webhook'),

    path("orders/paypal/<int:order_id>/", paypal_payment, name="paypal-payment"),

    path('payment/success/<int:order_id>/', payment_success, name='payment_success'),
    path('payment/cancel/<int:order_id>/', payment_cancel, name='payment_cancel'),
    path('save-location/', save_location, name='save_location'),

]
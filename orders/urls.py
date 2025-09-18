# orders/urls.py
from django.urls import path

from .views import (
    # Orders & addresses
    order_create,
    order_confirmation,
    order_edit,
    get_location_info,
    save_location,
    geo_autocomplete,

    # Payments: Stripe / Paystack / PayPal
    stripe_checkout,
    Stripe_payment_success,  # we expose as "stripe_payment_success" below
    stripe_webhook,

    paystack_checkout,
    paystack_payment_confirm,
    paystack_webhook,

    paypal_checkout,
    paypal_execute,
    paypal_payment,
    paypal_webhook,

    # Generic payment result pages
    payment_success,
    payment_cancel,

    # Tracking & driver endpoints
    track_order,
    driver_deliveries_page,
    driver_deliveries_api,
    driver_location_api,
    driver_action_api,
    driver_route_api,
    delivery_pings_api,
)

app_name = "orders"

urlpatterns = [
    # ----- Orders & address helpers -----
    path("create/", order_create, name="order_create"),
    path("confirmation/<int:order_id>/", order_confirmation, name="order_confirmation"),
    path("edit/<int:order_id>/", order_edit, name="order_edit"),
    path("api/reverse-geocode/", get_location_info, name="reverse_geocode"),
    path("api/geo/autocomplete/", geo_autocomplete, name="geo-autocomplete"),
    path("save-location/", save_location, name="save_location"),

    # ----- Stripe (dedicated names/paths) -----
    path("stripe/<int:order_id>/", stripe_checkout, name="stripe_checkout"),
    path("stripe/success/<int:order_id>/", Stripe_payment_success, name="stripe_payment_success"),
    path("webhook/stripe/", stripe_webhook, name="stripe_webhook"),

    # ----- Paystack -----
    path("paystack/<int:order_id>/", paystack_checkout, name="paystack_checkout"),
    # Client confirmation after verifying TX reference on your server
    path("paystack/confirm/", paystack_payment_confirm, name="paystack_payment_confirm"),
    # Stable webhook endpoint for Paystack events
    path("webhook/paystack/", paystack_webhook, name="paystack_webhook"),

    # ----- PayPal -----
    path("paypal/<int:order_id>/", paypal_checkout, name="paypal_checkout"),
    path("paypal/execute/<int:order_id>/", paypal_execute, name="paypal_execute"),
    path("webhook/paypal/", paypal_webhook, name="paypal_webhook"),
    path("paypal/payment/<int:order_id>/", paypal_payment, name="paypal-payment"),

    # ----- Generic payment result pages (shared UI) -----
    path("payment/success/<int:order_id>/", payment_success, name="payment_success"),
    path("payment/cancel/<int:order_id>/", payment_cancel, name="payment_cancel"),

    # ----- Order tracking & driver endpoints -----
    path("orders/<int:order_id>/track/", track_order, name="order-track"),
    path("driver/deliveries/", driver_deliveries_page, name="driver-deliveries"),          # HTML
    path("apis/driver/deliveries/", driver_deliveries_api, name="driver-deliveries-api"),  # JSON
    path("apis/driver/location/", driver_location_api, name="driver-location-api"),
    path("apis/driver/action/", driver_action_api, name="driver-action-api"),
    path("apis/driver/route/<int:delivery_id>/", driver_route_api, name="driver-route-api"),
    path("apis/delivery/<int:delivery_id>/pings/", delivery_pings_api, name="delivery-pings-api"),
]

# orders/urls.py
from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    # Orders (HTML)
    path("create/", views.order_create, name="order_create"),
    path("confirmation/<int:order_id>/", views.order_confirmation, name="order_confirmation"),
    path("edit/<int:order_id>/", views.order_edit, name="order_edit"),
    path("orders/<int:order_id>/track/", views.track_order, name="order-track"),

    # Location helpers
    path("api/reverse-geocode/", views.get_location_info, name="reverse_geocode"),
    path("api/geo/autocomplete/", views.geo_autocomplete, name="geo-autocomplete"),
    path("save-location/", views.save_location, name="save_location"),

    # Stripe
    path("stripe/<int:order_id>/", views.stripe_checkout, name="stripe_checkout"),
    path("stripe/success/<int:order_id>/", views.Stripe_payment_success, name="stripe-payment-success"),
    path("webhook/stripe/", views.stripe_webhook, name="stripe-webhook"),

    # Paystack
    path("paystack/<int:order_id>/", views.paystack_checkout, name="paystack_checkout"),
    path("paystack/confirm/", views.paystack_payment_confirm, name="paystack_payment_confirm"),
    path("webhook/paystack/", views.paystack_webhook, name="paystack-webhook"),

    # PayPal
    path("paypal/<int:order_id>/", views.paypal_checkout, name="paypal_checkout"),
    path("paypal/execute/<int:order_id>/", views.paypal_execute, name="paypal_execute"),
    path("webhook/paypal/", views.paypal_webhook, name="paypal-webhook"),
    path("orders/paypal/<int:order_id>/", views.paypal_payment, name="paypal-payment"),

    # Generic payment result pages (if you still use them)
    path("payment/success/<int:order_id>/", views.payment_success, name="payment_success"),
    path("payment/cancel/<int:order_id>/", views.payment_cancel, name="payment_cancel"),

    # Driver UI + APIs
    path("driver/deliveries/", views.driver_deliveries_page, name="driver-deliveries"),            # HTML page
    path("apis/driver/deliveries/", views.driver_deliveries_api, name="driver-deliveries-api"),   # JSON
    path("apis/driver/location/", views.driver_location_api, name="driver-location-api"),
    path("apis/driver/action/", views.driver_action_api, name="driver-action-api"),
    path("apis/driver/route/<int:delivery_id>/", views.driver_route_api, name="driver-route-api"),
]

# Optional: include delivery pings API if present in views
if hasattr(views, "delivery_pings_api"):
    urlpatterns.append(
        path("apis/delivery/<int:delivery_id>/pings/", views.delivery_pings_api, name="delivery-pings-api")
    )

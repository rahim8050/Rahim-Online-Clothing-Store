from django.urls import path
from .views import (
    order_create,
    order_confirmation,
    stripe_checkout,
    paypal_payment,
    paypal_execute,
    payment_success,
    payment_cancel,
)

app_name = "orders"

urlpatterns = [
    path('create', order_create, name="order_create"),
    path("confirmation/<int:order_id>", order_confirmation, name="order_confirmation"),
    path('stripe/<int:order_id>/', stripe_checkout, name='stripe_checkout'),
    path('paypal/<int:order_id>/', paypal_payment, name='paypal_payment'),
    path('paypal/execute/<int:order_id>/', paypal_execute, name='paypal_execute'),
    path('payment/success/<int:order_id>/', payment_success, name='payment_success'),
    path('payment/cancel/<int:order_id>/', payment_cancel, name='payment_cancel'),
]
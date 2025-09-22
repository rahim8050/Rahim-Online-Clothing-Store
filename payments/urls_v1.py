from django.urls import path

from .views_v1 import CheckoutInitV1

urlpatterns = [
    path("checkout/", CheckoutInitV1.as_view(), name="v1-payments-checkout"),
]

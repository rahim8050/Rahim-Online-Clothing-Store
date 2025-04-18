from django.urls import path
from . import views

app_name = "Mpesa"

urlpatterns = [
    path('trigger_mpesa_payment/', views.trigger_mpesa_payment, name='trigger-payment'),
    path('callback_mpesa_payment/', views.callback_mpesa_payment, name='callback-handler'),
]
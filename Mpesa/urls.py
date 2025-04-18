from django.urls import path

from Mpesa import views
from orders.urls import app_name
from users.urls import urlpatterns
app_name = "Mpesa"
urlpatterns = [
                path('trigger', views.trigger_mpesa_payment, name='home'),
                path('callback', views.callback_mpesa_payment, name='home'),
]
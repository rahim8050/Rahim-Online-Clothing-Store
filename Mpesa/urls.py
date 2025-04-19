from django.urls import path
from . import views

app_name = "Mpesa"

urlpatterns = [
    path('trigger/', views.trigger, name='trigger-payment'),
    path('mpesa/callback-handler/', views.callback, name='callback-handler'),
]
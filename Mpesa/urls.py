from django.urls import path
from . import views
app_name = "Mpesa"

urlpatterns = [
    # path('', views.mpesa, name='mpesa'),
    # path('trigger/', views.trigger, name='trigger-payment'),
    # path('mpesa/callback/', views.callback, name='mpesa-callback'),
      path('trigger/', views.trigger_stk_push, name='mpesa_trigger'),
    path('callback/', views.stk_callback, name='mpesa_callback'),
]
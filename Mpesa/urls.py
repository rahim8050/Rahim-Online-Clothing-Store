from typing import List
from django.urls.resolvers import URLPattern


app_name = "Mpesa"

urlpatterns: List[URLPattern] = [
    # path('', views.mpesa, name='mpesa'),
    # path('trigger/', views.trigger, name='trigger-payment'),
    # path('mpesa/callback/', views.callback, name='mpesa-callback'),
    # path('trigger/<int:id>/', views.stk_push, name='mpesa_trigger'),
    # path('trigger/', views.daraja_stk_push, name='daraja_stk_push'),
    # path('callback/', views.stk_callback, name='mpesa_callback'),
    # path('payment<int:order_id>/', views.mpesa_payment, name='mpesa_payment'),
]

from django.urls import  path
from .views import cart_add, cart_detail, cart_remove, cart_count,cart_increment, cart_decrement, get_cart_data

app_name = 'cart'

urlpatterns = [
    path('', cart_detail, name='cart_detail'),
    path('add/<int:product_id>/', cart_add, name='cart_add'),
    path('count/', cart_count, name='cart_count'),
    path("remove/<int:product_id>/",cart_remove,name='cart_remove'),
    path('increment/<int:product_id>/', cart_increment, name='cart_increment'),
    path('decrement/<int:product_id>/', cart_decrement, name='cart_decrement'),
    

]
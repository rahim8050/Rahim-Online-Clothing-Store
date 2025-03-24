
from django.urls import path

from cart.urls import app_name
from . import views
from .views import SearchProduct
app_name = 'product_app'
urlpatterns = [
path('Product/search', SearchProduct, name='SearchProduct'),



]

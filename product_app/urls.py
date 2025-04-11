from django.urls import path
from .views import product_list, SearchProduct  # Combined imports

app_name = 'product_app'  # Namespace for your app

urlpatterns = [
    # Proper path syntax with name parameter
path('Product/search/', SearchProduct, name='SearchProduct')
]


from django.urls import path
from .views import  SearchProduct,product_detail  # Combined imports

app_name = 'product_app'  # Namespace for your app

urlpatterns = [
    # Proper path syntax with name parameter
path('product/<int:id>/<slug:slug>/',product_detail, name='product_detail'),    
path('Product/search/', SearchProduct, name='SearchProduct'),

]


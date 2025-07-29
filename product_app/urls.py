from django.urls import path
from .views import  SearchProduct,product_detail  

app_name = 'product_app'  

urlpatterns = [
 
path('product/<int:id>/<slug:slug>/',product_detail, name='product_detail'),    
path('Product/search/', SearchProduct, name='SearchProduct'),

]


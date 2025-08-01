"""
URL configuration for CodeAlpa_Online_ClothesStore project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""


from django.contrib import admin
from django.urls import path,include
from product_app import views
from django.conf import settings
from django.conf.urls.static import static
from orders.views import paystack_webhook

urlpatterns = [
                  path('admin/', admin.site.urls),
                  path('utilities/', include('utilities.urls')), 
                  path('cart/', include('cart.urls')),
                  path('orders/', include("orders.urls",namespace='orders')),
                  # path('mpesa/', include('Mpesa.urls')),  # [Inactive] Preserved for future testing
                  path('', views.product_list, name='index'),
                  

                  path('webhook/paystack/', paystack_webhook, name='paystack_webhook'),  # ✅ direct path, no include

                  path('<slug:category_slug>/', views.product_list, name='product_list_by_category'),
                #   path('category/<slug:slug>/', views.product_list, name='product_list_by_category'),
                  path('products/search/', views.SearchProduct, name='product_search'),
                  path('users/', include("users.urls")),
                  path('users/', include('django.contrib.auth.urls')), 
                  path('products/', include('product_app.urls', namespace='product_app')),  # Fixed syntax
                  path('accounts/profile/', views.profile, name='profile'),
                
   




]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

      
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from product_app.models import Product
from .models import Cart,CartItem

@require_POST
def cart_add(request, product_id):
    cart_id =request.session.get('cart_id')
    if cart_id:
        try:
            cart = Cart.objects.get(id=cart_id)
        except Cart.DoesNotExist:
            cart =Cart.objects.create()
        else:
            cart = Cart.objects.create()
            request.session['cart_id'] = cart.id

        product = get_object_or_404(Product, id=product_id)

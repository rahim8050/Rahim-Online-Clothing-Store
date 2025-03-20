from django.shortcuts import render, redirect
from  cart.models import Cart
# Create your views here.
def order_create(request):
    Cart = None
    cart_id = request.session.get('cart_id')
    if cart_id:
        cart = Cart.object.get(id=cart_id)

        if not cart or not cart.items.exists():
            return redirect('cart:cart_detail')
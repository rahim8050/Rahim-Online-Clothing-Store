
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from product_app.models import Product
from .models import Cart,CartItem
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.urls import reverse_lazy

@require_POST
@login_required
def cart_add(request, product_id):
     if not request.user.is_authenticated:
        messages.warning(request, 'Please log in to add items to your cart.')
        return reverse_lazy('users:login') 
     cart_id = request.session.get('cart_id')

     if cart_id:
        try:
            cart = Cart.objects.get(id=cart_id)
        except Cart.DoesNotExist:
            cart = Cart.objects.create()
     else:
        
        cart = Cart.objects.create()
        request.session['cart_id'] = cart.id

     product = get_object_or_404(Product, id=product_id)

     cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

     if not created:
        cart_item.quantity += 1

     cart_item.save()
     request.session['cart_count'] = request.session.get('cart_count', 0) + 1

     response_data = {
        "success": True,
        "message": f'Added {product.name} to cart'
    }

     return JsonResponse(response_data)
# def cart_add(request, product_id):
#     if not request.user.is_authenticated:
#         messages.warning(self.request, 'Please log in to add items to your cart.')
#         return redirect('users:login') 
    
#     cart_id = request.session.get('cart_id')

#     if cart_id:
#         try:
#             cart = Cart.objects.get(id=cart_id)
#         except Cart.DoesNotExist:
#             cart = Cart.objects.create(user=request.user)  # Associate with user
#     else:
#         cart = Cart.objects.create(user=request.user)  # Associate with user
#         request.session['cart_id'] = cart.id

#     product = get_object_or_404(Product, id=product_id)

#     cart_item, created = CartItem.objects.get_or_create(
#         cart=cart, 
#         product=product,
#         defaults={'user': request.user}  # Associate with user
#     )

#     if not created:
#         cart_item.quantity += 1
#         cart_item.save()

#     request.session['cart_count'] = request.session.get('cart_count', 0) + 1

#     response_data = {
#         "success": True,
#         "message": f'Added {product.name} to cart',
#         "cart_count": request.session['cart_count']
#     }

#     return JsonResponse(response_data)







def cart_count(request):
    count = 0
    cart_id = request.session.get('cart_id')

    if cart_id:
        try:
            cart = Cart.objects.get(id=cart_id)
            count = cart.total_items()
        except Cart.DoesNotExist:
            pass

    return JsonResponse({'count': count})



def cart_detail(request):
    try:
        # Get cart from session
        cart_id = request.session.get('cart_id')
        cart = Cart.objects.get(id=cart_id)

        if not cart.items.exists():
            return redirect('products:list')  # Return empty cart redirect

        return render(request, 'cart/cart_detail.html', {'cart': cart})

    except (Cart.DoesNotExist, KeyError):
        # Clean up invalid cart session
        if 'cart_id' in request.session:
            del request.session['cart_id']
        return render(request, 'cart/cart_detail.html', {'cart': None})

# def cart_detail(request):
#        cart_id =request.session.get('cart_id')
#        if cart_id:
#               cart = get_object_or_404(Cart, id=cart_id)
#               if not cart or not cart.items.exists():
#                   cart = None
#               return render(request, 'cart/cart_detail.html', {'cart': cart})





def cart_remove(request, product_id):
    cart_id = request.session.get('cart_id')

    if not cart_id:  # No cart exists
        return redirect("cart:cart_detail")

    try:
        cart = Cart.objects.get(id=cart_id)
        # Correct lookup: Get CartItem by PRODUCT ID, not CartItem ID
        item = CartItem.objects.get(cart=cart, product__id=product_id)
        item.delete()

        # Delete cart if empty and clean session
        if not cart.items.exists():
            cart.delete()
            del request.session['cart_id']
            request.session.modified = True

    except (Cart.DoesNotExist, CartItem.DoesNotExist):
        # Handle missing cart or item gracefully
        if 'cart_id' in request.session:
            del request.session['cart_id']
        return redirect("cart:cart_detail")

    return redirect("cart:cart_detail")
# def cart_remove(request, product_id):
#     cart_id = request.session.get('cart_id')
#     cart = get_object_or_404(Cart, id=cart_id)
#     item = get_object_or_404(CartItem, id=product_id,cart=cart)
#     item.delete()
#     return redirect("cart:cart_detail")



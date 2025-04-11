      
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from product_app.models import Product
from .models import Cart,CartItem

@require_POST





def cart_add(request, product_id):
    # Get or create cart with proper session handling
    cart_id = request.session.get('cart_id')

    # 1. Fix session persistence for new carts
    if cart_id:
        try:
            cart = Cart.objects.get(id=cart_id)
        except Cart.DoesNotExist:
            # Session contained invalid cart ID - create new one and update session
            cart = Cart.objects.create()
            request.session['cart_id'] = cart.id
            request.session.modified = True  # Force session save
    else:
        # No existing cart - create new one
        cart = Cart.objects.create()
        request.session['cart_id'] = cart.id
        request.session.modified = True  # Force session save

    # 2. Get product with proper error handling
    product = get_object_or_404(Product, id=product_id)

    # 3. Update or create cart item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )

    if not created:
        cart_item.quantity += 1
        cart_item.save()

    # 4. Return proper JSON response
    return JsonResponse({
        "success": True,
        "message": f'Added {product.name} to cart',
        "cart_total_items": cart.total_items()
    })
# def cart_add(request, product_id):
#     cart_id = request.session.get('cart_id')
#
#     if cart_id:
#         try:
#             cart = Cart.objects.get(id=cart_id)
#         except Cart.DoesNotExist:
#             cart = Cart.objects.create()
#     else:
#         cart = Cart.objects.create()
#         request.session['cart_id'] = cart.id
#
#     product = get_object_or_404(Product, id=product_id)
#
#     cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
#
#     if not created:
#         cart_item.quantity += 1
#
#     cart_item.save()
#
#     response_data = {
#         "success": True,
#         "message": f'Added {product.name} to cart'
#     }
#
#     return JsonResponse(response_data)






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
    cart = get_object_or_404(Cart, id=cart_id)
    item = get_object_or_404(CartItem, id=product_id,cart=cart)
    item.delete()
    return redirect("cart:cart_detail")



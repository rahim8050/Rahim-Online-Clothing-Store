
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from product_app.models import Product
from .models import Cart,CartItem
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
import traceback



@require_POST
def cart_add(request, product_id):
    try:
        cart_id = request.session.get('cart_id')

        if cart_id:
            cart, created = Cart.objects.get_or_create(id=cart_id)
        else:
            cart = Cart.objects.create()
            request.session['cart_id'] = cart.id

        product = get_object_or_404(Product, id=product_id)

        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            cart_item.quantity += 1
        cart_item.save()

        request.session['cart_count'] = request.session.get('cart_count', 0) + 1

        return JsonResponse({
            "success": True,
            "message": f'Added {product.name} to cart'
        })

    except Exception as e:
        print("Error in cart_add:", e)
        traceback.print_exc()
        return JsonResponse({
            "success": False,
            "message": "Something went wrong. Please try again."
        }, status=500)
        
        
def cart_count(request):
    cart_id = request.session.get('cart_id')

    if not cart_id:
        return JsonResponse({'count': 0})

    try:
        cart = Cart.objects.get(id=cart_id)
        total_items = sum(item.quantity for item in cart.items.all())  # Count quantity across items
        return JsonResponse({'count': total_items})
    except Cart.DoesNotExist:
        return JsonResponse({'count': 0})

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







# def cart_remove(request, product_id):
#     cart_id = request.session.get('cart_id')

#     if not cart_id:  # No cart exists
#         return redirect("cart:cart_detail")

#     try:
#         cart = Cart.objects.get(id=cart_id)
#         # Correct lookup: Get CartItem by PRODUCT ID, not CartItem ID
#         item = CartItem.objects.get(cart=cart, product__id=product_id)
#         item.delete()

#         # Delete cart if empty and clean session
#         if not cart.items.exists():
#             cart.delete()
#             del request.session['cart_id']
#             request.session.modified = True

#     except (Cart.DoesNotExist, CartItem.DoesNotExist):
#         # Handle missing cart or item gracefully
#         if 'cart_id' in request.session:
#             del request.session['cart_id']
#         return redirect("cart:cart_detail")

#     return redirect("cart:cart_detail")
def cart_remove(request, product_id):
    cart_id = request.session.get('cart_id')

    if not cart_id:  # No cart exists
        return redirect("cart:cart_detail")

    try:
        cart = Cart.objects.get(id=cart_id)
        # Get the specific cart item for this product
        try:
            item = CartItem.objects.get(cart=cart, product__id=product_id)
            item.delete()
            
            # Update cart count in session
            if 'cart_count' in request.session:
                request.session['cart_count'] = max(0, request.session['cart_count'] - item.quantity)
            
            # Delete cart if empty and clean session
            if not cart.items.exists():
                cart.delete()
                del request.session['cart_id']
                if 'cart_count' in request.session:
                    del request.session['cart_count']
        except CartItem.DoesNotExist:
            # The specific item wasn't found - just continue to cart
            pass

    except Cart.DoesNotExist:
        # Clean up session if cart doesn't exist
        if 'cart_id' in request.session:
            del request.session['cart_id']
        if 'cart_count' in request.session:
            del request.session['cart_count']

    return redirect("cart:cart_detail")
@require_POST
def cart_increment(request, product_id):
    """Increase quantity of a specific cart item by 1"""
    cart_id = request.session.get('cart_id')
    if not cart_id:
        return redirect("cart:cart_detail")
    
    try:
        cart = Cart.objects.get(id=cart_id)
        item = CartItem.objects.get(cart=cart, product__id=product_id)
        
        # Increase quantity
        item.quantity += 1
        item.save()
        
        # Update session cart_count
        if 'cart_count' in request.session:
            request.session['cart_count'] += 1
        
        messages.success(request, f"Added one more {item.product.name}")
        
    except (Cart.DoesNotExist, CartItem.DoesNotExist):
        messages.error(request, "Item not found in cart")
    
    return redirect("cart:cart_detail")

@require_POST
def cart_decrement(request, product_id):
    """Decrease quantity of a specific cart item by 1"""
    cart_id = request.session.get('cart_id')
    if not cart_id:
        return redirect("cart:cart_detail")
    
    try:
        cart = Cart.objects.get(id=cart_id)
        item = CartItem.objects.get(cart=cart, product__id=product_id)
        
        # Decrease quantity or remove if 1
        if item.quantity > 1:
            item.quantity -= 1
            item.save()
            
            # Update session cart_count
            if 'cart_count' in request.session:
                request.session['cart_count'] = max(0, request.session['cart_count'] - 1)
            
            messages.info(request, f"Removed one {item.product.name}")
        else:
            # Remove item completely if quantity would become 0
            item.delete()
            
            # Update session cart_count
            if 'cart_count' in request.session:
                request.session['cart_count'] = max(0, request.session['cart_count'] - 1)
            
            messages.info(request, f"Removed {item.product.name} from cart")
            
            # Delete cart if empty
            if not cart.items.exists():
                cart.delete()
                del request.session['cart_id']
        
    except (Cart.DoesNotExist, CartItem.DoesNotExist):
        messages.error(request, "Item not found in cart")
    
    return redirect("cart:cart_detail")




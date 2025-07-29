
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils.safestring import mark_safe
import json
from product_app.models import Product
from .models import Cart,CartItem
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
import traceback
from orders.forms import OrderForm



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
        cart_id = request.session.get('cart_id')
        cart = Cart.objects.get(id=cart_id)

        if not cart.items.exists():
            return redirect('products:list')

        cart_items = cart.items.select_related('product')
        total_price = sum(item.product.price * item.quantity for item in cart_items)
 
        order_form = OrderForm()

        return render(request, 'cart/cart_detail.html', {
            'cart': cart,
            'cart_items': cart_items,
            'total_price': total_price,
            'order_form': order_form,      
        })

    except (Cart.DoesNotExist, KeyError):
        request.session.pop('cart_id', None)
        return render(request, 'cart/cart_detail.html', {
            'cart': None,
            'cart_items': [],
            'total_price': 0,
            'order_form': OrderForm(),     
        })


    except (Cart.DoesNotExist, KeyError):
        if 'cart_id' in request.session:
            del request.session['cart_id']
        return render(request, 'cart/cart_detail.html', {
            'cart': None,
            'cart_items': [],
            'total_price': 0
        })




def get_cart_data(request):
    cart_id = request.session.get('cart_id')
    try:
        cart = Cart.objects.get(id=cart_id)
        cart_items = []
        for item in cart.items.select_related('product'):
            cart_items.append({
                'id': item.id,
                'product': {
                    'id': item.product.id,
                    'name': item.product.name,
                    'description': item.product.description,
                    'price': float(item.product.price),
                    'image_url': item.product.image.url if item.product.image else '',
                    'detail_url': item.product.get_absolute_url(),  
                },
                'quantity': item.quantity,
            })

        return JsonResponse({'cart_items': cart_items, 'exists': True})
    
    except Cart.DoesNotExist:
        return JsonResponse({'cart_items': [], 'exists': False})




def cart_remove(request, product_id):
    cart_id = request.session.get('cart_id')

    if not cart_id:  
        return redirect("cart:cart_detail")

    try:
        cart = Cart.objects.get(id=cart_id)
        
        try:
            item = CartItem.objects.get(cart=cart, product__id=product_id)
            item.delete()
            
            
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




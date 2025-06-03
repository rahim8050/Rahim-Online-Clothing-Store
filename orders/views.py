from django.shortcuts import render, redirect, get_object_or_404
from  cart.models import Cart
from orders.forms import OrderForm
from orders.models import Order, OrderItem
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db import transaction



# Create your views here.
# def order_create(request):
#     # cart = None
#     # cart = Cart.objects.get(user=request.user)
#     cart_id = request.session.get('cart_id')

#     # Check if cart exists and is valid
#     if cart_id:
#         try:
#             cart = Cart.objects.get(id=cart_id)
#             if not cart.items.exists():  # Redirect if cart is empty
#                 return redirect("cart:cart_detail")
#         except Cart.DoesNotExist:
#             del request.session['cart_id']
#             return redirect("cart:cart_detail")
# # this form is to be validated that the user must be logged in to place an order
# # this took me a while to figure out that the form was the issue and not the view

#     # Handle POST (form submission)
   
#         form = OrderForm(request.POST)
#         if form.is_valid():
#             # Check if cart is still valid
#             if not cart:  # Add this check!
#                 return redirect("cart:cart_detail")  # Redirect if cart is missing

#             # Save order and process items
#             order = form.save(commit=False)
#             order.save()

#             for item in cart.items.all():  # Now safe to use cart.items
#                 OrderItem.objects.create(
#                     order=order,
#                     product=item.product,
#                     price=item.product.price,
#                     quantity=item.quantity
#                 )

#             # Clean up cart
#             cart.delete()
#             del request.session["cart_id"]
#             return redirect("orders:order_confirmation", order.id)
#     else:
#         form = OrderForm()

#     return render(request, "orders/order_create.html", {
#         "cart": cart,
#         "form": form
#     })


@require_http_methods(["GET", "POST"])  # Explicitly allow GET and POST
def order_create(request):
    # Authentication check (like enroll_program)
    if not request.user.is_authenticated:
        messages.warning(request, "Please log in to place an order")
        return redirect('login')  # Use your login URL name

    # Cart handling (similar to program retrieval in enroll_program)
    cart_id = request.session.get('cart_id')
    cart = None
    
    # Validate cart existence (like program validation)
    if cart_id:
        try:
            cart = get_object_or_404(Cart, id=cart_id)
            if not cart.items.exists():
                messages.warning(request, "Your cart is empty")
                return redirect("cart:cart_detail")
        except Cart.DoesNotExist:
            if 'cart_id' in request.session:
                del request.session['cart_id']
            messages.warning(request, "Your cart has expired")
            return redirect("cart:cart_detail")
    else:
        messages.warning(request, "Your cart is empty")
        return redirect("cart:cart_detail")

    # Order processing (similar to enrollment creation)
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():  # Ensure database integrity
                    # Create order (like enrollment creation)
                    order = form.save(commit=False)
                    order.user = request.user  # Associate user
                    order.save()

                    # Create order items (like enrollment relationship)
                    for item in cart.items.all():
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            price=item.product.price,
                            quantity=item.quantity
                        )

                    # Cleanup (similar to post-enrollment actions)
                    cart.delete()
                    if 'cart_id' in request.session:
                        del request.session['cart_id']
                    if 'cart_count' in request.session:
                        del request.session['cart_count']

                    messages.success(request, "Order placed successfully!")
                    return redirect("orders:order_confirmation", order.id)
                    
            except Exception as e:
                messages.error(request, f"Order failed: {str(e)}")
        else:
            # Form validation failed
            messages.error(request, "Please correct the errors in your order form")
    
  
    else:
        # Pre-fill form with user data
        initial_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        }
        # Add profile data if available
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            initial_data.update({
                'phone_number': profile.phone,
                'address': profile.address,
                'postal_code': profile.postal_code,
                'city': profile.city,
            })
        form = OrderForm(initial=initial_data)

    return render(request, "orders/order_create.html", {
        "cart": cart,
        "form": form
    })

   
# @login_required
# def order_create(request):
#     # Cart handling logic
#     cart_id = request.session.get('cart_id')
#     cart = None

#     if cart_id:
#         try:
#             cart = Cart.objects.get(id=cart_id)
#             if not cart.items.exists():
#                 return redirect("cart:cart_detail")
#         except Cart.DoesNotExist:
#             # Clean up invalid session data
#             if 'cart_id' in request.session:
#                 del request.session['cart_id']
#             return redirect("cart:cart_detail")
#     else:
#         return redirect("cart:cart_detail")

#     # Ensure we have a valid cart at this point
#     if cart is None:
#         return redirect("cart:cart_detail")

#     # Handle POST request
#     if request.method == 'POST':
#         form = OrderForm(request.POST)
#         if form.is_valid():
#             order = form.save(commit=False)
            
#             # Add user association if authenticated
#             if request.user.is_authenticated:
#                 order.user = request.user
                
#             order.save()

#             # Create order items
#             for item in cart.items.all():
#                 OrderItem.objects.create(
#                     order=order,
#                     product=item.product,
#                     price=item.product.price,
#                     quantity=item.quantity
#                 )

#             # Clean up cart and session
#             cart.delete()
#             if 'cart_id' in request.session:
#                 del request.session['cart_id']
#             if 'cart_count' in request.session:
#                 del request.session['cart_count']

#             return redirect("orders:order_confirmation", order.id)
#     else:
#         form = OrderForm()

#     # Always return a proper HttpResponse object
#     return render(request, "orders/order_create.html", {
#         "cart": cart,
#         "form": form
#     })

# def order_create(request):
#     cart = None
#     cart_id = request.session.get('cart_id')
#     if cart_id:
#         cart = Cart.objects.get(id=cart_id)
#
#         if not cart or not cart.items.exists():
#             return redirect('cart:cart_detail')
#         if request.method == "POST":
#             form = OrderForm(request.POST)
#             if form.is_valid():
#                 order = form.save(commit=False)
#                 order.save()
#                 for item in cart.items.all():
#                     OrderItem.objects.create(
#                         order=order,
#                         product=item.product,
#                         price=item.product.price,
#                         quantity=item.quantity
#                     )
#                     cart.delete()
#                     del request.session["cart_id"]
#                     return redirect("orders:order_confirmation", order.id)
#     else:
#         form = OrderForm()
#         return render (request,"orders/order_create.html",{"form":form,"cart":cart})


def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "orders/order_confirmation.html", {"order":order})
from django.shortcuts import render, redirect, get_object_or_404
from  cart.models import Cart
from orders.forms import OrderForm
from orders.models import Order, OrderItem
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from orders.models import Order
from django.db import transaction
from django.conf import settings
from django.http import JsonResponse
from orders.utils import reverse_geocode
# Create your views here.



@require_http_methods(["GET", "POST"])
# def order_create(request):
#     print("METHOD:", request.method)

#     #  Check if user is logged in
#     if not request.user.is_authenticated:
#         messages.warning(request, "Please log in to place an order")
#         return redirect('users:login')

#     #  Get cart
#     cart_id = request.session.get('cart_id')
#     cart = None

#     if cart_id:
#         try:
#             cart = get_object_or_404(Cart, id=cart_id)
#             if not cart.items.exists():
#                 messages.warning(request, "Your cart is empty")
#                 return redirect("cart:cart_detail")
#         except Cart.DoesNotExist:
#             request.session.pop('cart_id', None)
#             messages.warning(request, "Your cart has expired")
#             return redirect("cart:cart_detail")
#     else:
#         messages.warning(request, "Your cart is empty")
#         return redirect("cart:cart_detail")

#     #  Handle POST
#     if request.method == 'POST' and 'full_name' in request.POST:
#         form = OrderForm(request.POST)
#         if form.is_valid():
#             try:
#                 with transaction.atomic():
#                     order = form.save(commit=False)
#                     order.user = request.user
#                     order.save()

#                     # Save cart items into order
#                     for item in cart.items.all():
#                         OrderItem.objects.create(
#                             order=order,
#                             product=item.product,
#                             price=item.product.price,
#                             quantity=item.quantity
#                         )

#                     # Clear cart
#                     cart.delete()
#                     request.session.pop('cart_id', None)
#                     request.session.pop('cart_count', None)

#                     messages.success(request, "Order placed successfully!")
#                     return redirect("orders:order_confirmation", order.id)
#             except Exception as e:
#                 messages.error(request, f"Order failed: {str(e)}")
#         else:
#             messages.error(request, "Please correct the errors in your order form")
#     else:
#         form = OrderForm()

#     return render(request, "orders/order_create.html", {
#     "form": form,
#     "cart": cart,
#     "geoapify_api_key": settings.GEOAPIFY_API_KEY,
#     "excluded_fields": ["payment_method", "mpesa_phone_number", "address", "latitude", "longitude"],  # ✅
# })
@require_http_methods(["GET", "POST"])
def order_create(request):
    print("METHOD:", request.method)

    #  Check if user is logged in
    if not request.user.is_authenticated:
        messages.warning(request, "Please log in to place an order")
        return redirect('users:login')

    #  Get cart
    cart_id = request.session.get('cart_id')
    cart = None

    if cart_id:
        try:
            cart = get_object_or_404(Cart, id=cart_id)
            if not cart.items.exists():
                messages.warning(request, "Your cart is empty")
                return redirect("cart:cart_detail")
        except Cart.DoesNotExist:
            request.session.pop('cart_id', None)
            messages.warning(request, "Your cart has expired")
            return redirect("cart:cart_detail")
    else:
        messages.warning(request, "Your cart is empty")
        return redirect("cart:cart_detail")

    #  Detect accidental/empty POST (browser resubmits or forced posts)
    if request.method == 'POST' and 'full_name' in request.POST:
        form = OrderForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    order = form.save(commit=False)
                    order.user = request.user
                    order.save()

                    # Save cart items into order
                    for item in cart.items.all():
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            price=item.product.price,
                            quantity=item.quantity
                        )

                    # Clear cart
                    cart.delete()
                    request.session.pop('cart_id', None)
                    request.session.pop('cart_count', None)

                    messages.success(request, "Order placed successfully!")
                    return redirect("orders:order_confirmation", order.id)
            except Exception as e:
                messages.error(request, f"Order failed: {str(e)}")
        else:
            messages.error(request, "Please correct the errors in your order form")
    else:
        # Initial GET or ignored POST
        form = OrderForm()

    return render(request, "orders/order_create.html", {
        "form": form,
        "cart": cart,
    })
    


def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "orders/order_confirmation.html", {"order":order})





def get_location_info(request):
    lat = request.GET.get("lat", "51.21709661403662")
    lon = request.GET.get("lon", "6.7782883744862374")

    data = reverse_geocode(lat, lon)
    return JsonResponse(data)

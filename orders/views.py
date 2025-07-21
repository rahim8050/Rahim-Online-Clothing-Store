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
def order_create(request):
    print("METHOD:", request.method)

    if not request.user.is_authenticated:
        messages.warning(request, "Please log in to place an order")
        return redirect('users:login')

    cart_id = request.session.get('cart_id')
    if not cart_id:
        messages.warning(request, "Your cart is empty")
        return redirect("cart:cart_detail")

    cart = get_object_or_404(Cart, id=cart_id)

    if not cart.items.exists():
        messages.warning(request, "Your cart is empty")
        return redirect("cart:cart_detail")

    if request.method == 'POST':
        selected_items = request.POST.getlist('selected_items')

        if selected_items:
            # Reset all items to unselected
            cart.items.update(is_selected=False)
            # Mark only selected items
            cart.items.filter(product_id__in=selected_items).update(is_selected=True)

        form = OrderForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    order = form.save(commit=False)
                    order.user = request.user
                    order.save()

                    # Fetch only selected items
                    cart_items = cart.items.filter(is_selected=True)

                    for item in cart_items:
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            price=item.product.price,
                            quantity=item.quantity
                        )

                    cart_items.delete()
                    if not cart.items.exists():
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
        form = OrderForm()

    # Prepare cart_items and total for rendering
    cart_items = cart.items.filter(is_selected=True)
    if not cart_items.exists():
        cart_items = cart.items.all()

    selected_total = sum(item.product.price * item.quantity for item in cart_items)

    return render(request, "orders/order_create.html", {
        "form": form,
        "cart": cart,
        "cart_items": cart_items,
        "selected_total": selected_total
    })
    


def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "orders/order_confirmation.html", {"order":order})





def get_location_info(request):
    lat = request.GET.get("lat", "51.21709661403662")
    lon = request.GET.get("lon", "6.7782883744862374")

    data = reverse_geocode(lat, lon)
    return JsonResponse(data)

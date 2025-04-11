from django.shortcuts import render, redirect, get_object_or_404
from  cart.models import Cart
from orders.forms import OrderForm
from orders.models import Order, OrderItem


# Create your views here.
def order_create(request):
    cart = None
    cart_id = request.session.get('cart_id')

    # Check if cart exists and is valid
    if cart_id:
        try:
            cart = Cart.objects.get(id=cart_id)
            if not cart.items.exists():
                return redirect("cart:cart_detail")
        except Cart.DoesNotExist:
            del request.session['cart_id']
            return redirect("cart:cart_detail")

    # Handle POST (form submission)
    if request.method == "POST":
        form = OrderForm(request.POST)
        if form.is_valid():
            # Save order and process items
            order = form.save(commit=False)
            order.save()

            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    price=item.product.price,
                    quantity=item.quantity
                )

            # Clean up cart
            cart.delete()
            del request.session["cart_id"]
            return redirect("orders:order_confirmation", order.id)
    else:
        # Handle GET (initial page load)
        form = OrderForm()

    # This return handles both:
    # - GET requests (fresh form)
    # - Invalid POST submissions (form with errors)
    return render(request, "orders/order_create.html", {
        "cart": cart,
        "form": form
    })
# def order_create(request):
#     cart = None
#     cart_id = request.session.get('cart_id')
#
#     if cart_id:
#         cart = Cart.objects.get(id=cart_id)
#
#         if not cart or not cart.items.exists():
#             return redirect("cart:cart_detail")
#
#     if request.method == "POST":
#         form = OrderForm(request.POST)
#         if form.is_valid():
#             order = form.save(commit=False)
#             order.save()
#
#             for item in cart.items.all():
#                 OrderItem.objects.create(
#                     order=order,
#                     product=item.product,
#                     price=item.product.price,
#                     quantity=item.quantity
#                 )
#             cart.delete()
#             del request.session["cart_id"]
#             return redirect("orders:order_confirmation", order.id)
#         else:
#             form = OrderForm()
#
#         return render(request, "orders/order_create.html", {
#             "cart": cart, "form": form
#         })
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
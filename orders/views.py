from django.shortcuts import render, redirect, get_object_or_404
from  cart.models import Cart
from orders.forms import OrderForm
from orders.models import Order, OrderItem
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from orders.models import Order
from django.db import transaction
from django.conf import settings
import stripe
import paypalrestsdk

# Configure Stripe and PayPal with keys from settings
stripe.api_key = settings.STRIPE_SECRET_KEY
paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET,
})
# Create your views here.



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


def stripe_checkout(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "kes",
                "product_data": {"name": f"Order {order.id}"},
                "unit_amount": int(order.get_total_cost()) * 100,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=request.build_absolute_uri(
            reverse("orders:payment_success", args=[order.id])
        ),
        cancel_url=request.build_absolute_uri(
            reverse("orders:payment_cancel", args=[order.id])
        ),
    )
    return redirect(session.url)


def paypal_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": request.build_absolute_uri(
                reverse("orders:paypal_execute", args=[order.id])
            ),
            "cancel_url": request.build_absolute_uri(
                reverse("orders:payment_cancel", args=[order.id])
            ),
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": f"Order {order.id}",
                    "sku": f"{order.id}",
                    "price": str(order.get_total_cost()),
                    "currency": "KES",
                    "quantity": 1,
                }]
            },
            "amount": {
                "total": str(order.get_total_cost()),
                "currency": "KES",
            },
            "description": f"Payment for Order {order.id}",
        }],
    })
    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                request.session["paypal_payment_id"] = payment.id
                return redirect(link.href)
    messages.error(request, "Unable to create PayPal payment")
    return redirect("orders:order_confirmation", order.id)


def paypal_execute(request, order_id):
    payment_id = request.session.get("paypal_payment_id")
    payer_id = request.GET.get("PayerID")
    if not payment_id or not payer_id:
        messages.error(request, "Invalid PayPal response")
        return redirect("orders:order_confirmation", order_id)
    payment = paypalrestsdk.Payment.find(payment_id)
    if payment.execute({"payer_id": payer_id}):
        order = get_object_or_404(Order, id=order_id)
        order.paid = True
        order.save()
        return redirect("orders:payment_success", order.id)
    else:
        messages.error(request, "PayPal payment execution failed")
        return redirect("orders:order_confirmation", order_id)


def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.paid = True
    order.save()
    return render(request, "payment_result.html", {"message": "Payment successful"})


def payment_cancel(request, order_id):
    return render(request, "payment_result.html", {"error": "Payment cancelled"})

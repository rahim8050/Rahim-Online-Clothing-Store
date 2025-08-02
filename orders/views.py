from django.shortcuts import render, redirect, get_object_or_404
from  cart.models import Cart
from orders.forms import OrderForm
from orders.models import Order, OrderItem
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.conf import settings
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from django.http import JsonResponse
from orders.utils import reverse_geocode
from .models import Transaction

import stripe
import paypalrestsdk
import requests
import json
import hmac
import hashlib

# Configure Stripe and PayPal with keys from settings
stripe.api_key = settings.STRIPE_SECRET_KEY
paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET,
})

# Create your views here.





logger = logging.getLogger(__name__)

@require_http_methods(["GET", "POST"])
def order_create(request):
    
    if not request.user.is_authenticated:
        #  messages.warning(request, "Please log in to place an order")
         return redirect('users:login')

    cart = None
    cart_id = request.session.get('cart_id')
    logger.info(f"Session cart_id: {cart_id}")

   
    if cart_id:
        try:
            cart = get_object_or_404(Cart, id=cart_id)
            logger.info(f"Cart found: {cart}")
        except Exception as e:
            logger.error(f"Cart retrieval failed: {e}")
            cart = None
    else:
        logger.info("No cart found in session")

    
    if not cart or not cart.items.exists():
        messages.warning(request, "Your cart is empty")
        return redirect("cart:cart_detail")

    error_msg = None
    form = None

    
    if request.method == "POST":
        selected_items = request.POST.getlist('selected_items')
        if selected_items:
            # Mark all items not selected
            cart.items.update(is_selected=False)
            # Mark only selected items
            cart.items.filter(product_id__in=selected_items).update(is_selected=True)

        # Check if order form fields are present in POST data
        has_form_data = any(name in request.POST for name in (
            'full_name', 'email', 'address', 'payment_method'
        ))

        if not has_form_data:
            
            form = OrderForm()
        else:
            # Real checkout submission
            form = OrderForm(request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        order = form.save(commit=False)
                        order.user = request.user
                        order.save()

                        # Create order items for selected cart items
                        for item in cart.items.filter(is_selected=True):
                            OrderItem.objects.create(
                                order=order,
                                product=item.product,
                                price=item.product.price,
                                quantity=item.quantity
                            )

                        # Remove checked-out items from cart
                        cart.items.filter(is_selected=True).delete()

                        # Delete cart and clear session if no items remain
                        if not cart.items.exists():
                            cart.delete()
                            request.session.pop('cart_id', None)

                        # Always clear cart count in session after order
                        request.session.pop('cart_count', None)

                    messages.success(request, "Order placed successfully!")
                    return redirect("orders:order_confirmation", order.id)

                except Exception as e:
                    logger.error(f"Order save failed: {e}")
                    messages.error(request, f"Order failed: {e}")
            else:
                error_msg = "Please correct the errors in your order form"

    else:
       
        form = OrderForm()

    
    if cart:
        cart_items = cart.items.filter(is_selected=True)
        if not cart_items.exists():
            cart_items = cart.items.all()
        selected_total = sum(i.product.price * i.quantity for i in cart_items)
    else:
        cart_items = []
        selected_total = 0

   
    return render(request, "orders/order_create.html", {
        "form": form,
        "cart": cart,
        "cart_items": cart_items,
        "selected_total": selected_total,
        "error_msg": error_msg,
        "geoapify_api_key": settings.GEOAPIFY_API_KEY,
    })
    


def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "orders/order_confirmation.html", {"order":order})






def get_location_info(request):
    lat = request.GET.get("lat", "51.21709661403662")
    lon = request.GET.get("lon", "6.7782883744862374")

    data = reverse_geocode(lat, lon)
    return JsonResponse(data)


def paystack_checkout(request, order_id):
    """Initialize a Paystack transaction for card or M-Pesa."""
    order = get_object_or_404(Order, id=order_id)

    payment_method = request.GET.get("payment_method")
    if payment_method not in {"card", "mpesa"}:
        messages.error(request, "Invalid payment method")
        return redirect("orders:order_confirmation", order.id)

    channel = "card" if payment_method == "card" else "mobile_money"
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    data = {
        "email": order.email,
        "amount": int(order.get_total_cost()) * 100,
        "callback_url": request.build_absolute_uri(
            reverse("orders:payment_success", args=[order.id])
        ),
        "metadata": {"order_id": order.id},
        "channels": [channel],
    }
    try:
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=data,
            headers=headers,
            timeout=30,
        )
        res_data = response.json()
        auth_url = res_data["data"]["authorization_url"]
        reference = res_data["data"]["reference"]
        Transaction.objects.create(
            user=order.user,
            amount=order.get_total_cost(),
            method=payment_method,
            gateway="paystack",
            status="pending",
            reference=reference,
        )
        return redirect(auth_url)
    except Exception:
        messages.error(request, "Unable to initialize Paystack payment")
    return redirect("orders:order_confirmation", order.id)

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
        metadata={
            "order_id": str(order.id),  
        },
        success_url=request.build_absolute_uri(
            reverse("orders:payment_success", args=[order.id])
        ) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.build_absolute_uri(
            reverse("orders:payment_cancel", args=[order.id])
        ),
    )

    return redirect(session.url)
# stripe payment callback
@login_required
def Stripe_payment_success(request, order_id):
    session_id = request.GET.get("session_id")

    if not session_id:
        return render(request, "orders/payment_failed.html", {
            "message": "No session ID provided."
        })

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        payment_intent = stripe.PaymentIntent.retrieve(session.payment_intent)
    except Exception as e:
        return render(request, "orders/payment_failed.html", {
            "message": f"Stripe error: {str(e)}"
        })

    # Get order
    order = get_object_or_404(Order, id=order_id)

    # Save payment details to order model
    order.payment_status = "paid"
    order.payment_intent_id = payment_intent.id
    order.stripe_receipt_url = payment_intent.charges.data[0].receipt_url
    order.save()

    return render(request, "orders/payment_success.html", {
        "order": order,
        "receipt_url": order.stripe_receipt_url
    })
    
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # Handles  events here
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        order_id = session.get("metadata", {}).get("order_id")

        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                order.payment_status = "paid"
                order.payment_intent_id = session.get("payment_intent")
                order.save()
            except Order.DoesNotExist:
                pass

    elif event['type'] == 'payment_intent.payment_failed':
        print(" Payment failed.")

    elif event['type'] == 'charge.refunded':
        print("🤦‍♀️ Refund processed.")

    return HttpResponse(status=200)


@csrf_exempt
def paystack_webhook(request):
    signature = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")
    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(), request.body, hashlib.sha512
    ).hexdigest()
    if not hmac.compare_digest(signature, computed):
        return HttpResponse(status=400)

    event = json.loads(request.body)
    event_type = event.get("event")
    data = event.get("data", {})
    reference = data.get("reference")
    order_id = data.get("metadata", {}).get("order_id")

    if event_type == "charge.success":
        Transaction.objects.filter(reference=reference).update(status="success")
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                order.paid = True
                order.save()
            except Order.DoesNotExist:
                pass
    elif event_type == "charge.failed":
        Transaction.objects.filter(reference=reference).update(status="failed")
    elif event_type == "charge.cancelled":
        Transaction.objects.filter(reference=reference).update(status="cancelled")

    return HttpResponse(status=200)
def paystack_payment_confirm(request):
    return render(request, "orders/paystack_confirm.html")


@csrf_exempt
def paypal_webhook(request):
    try:
        event = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)
    if event.get("event_type") == "PAYMENT.CAPTURE.COMPLETED":
        resource = event.get("resource", {})
        reference = resource.get("id")
        invoice = resource.get("invoice_id")
        Transaction.objects.filter(reference=reference).update(status="success")
        if invoice:
            try:
                order = Order.objects.get(id=invoice)
                order.paid = True
                order.save()
            except Order.DoesNotExist:
                pass
    return HttpResponse(status=200)

def paypal_checkout(request, order_id):
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
        Transaction.objects.create(
            user=order.user,
            amount=order.get_total_cost(),
            method="paypal",
            gateway="paypal",
            status="pending",
            reference=payment.id,
        )
        for link in payment.links:
            if link.rel == "approval_url":
                request.session["paypal_payment_id"] = payment.id
                return redirect(link.href)
    messages.error(request, "Unable to create PayPal payment")
    return redirect("orders:order_confirmation", order.id)

# paypal payment execution
def paypal_execute(request, order_id):
    # Ensure configuration happens here
    paypalrestsdk.configure({
        "mode": settings.PAYPAL_MODE,
        "client_id": settings.PAYPAL_CLIENT_ID,
        "client_secret": settings.PAYPAL_SECRET,
    })

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
        Transaction.objects.filter(reference=payment_id).update(status="success")
        return redirect("orders:payment_success", order.id)
    else:
        messages.error(request, "PayPal payment execution failed")
        return redirect("orders:order_confirmation", order_id)

def paypal_payment(request, order_id):
    paypalrestsdk.configure({
        "mode": settings.PAYPAL_MODE,
        "client_id": settings.PAYPAL_CLIENT_ID,
        "client_secret": settings.PAYPAL_CLIENT_SECRET,
    })

    order = get_object_or_404(Order, id=order_id)
    total_amount = str(order.get_total_cost())  # must be a string

    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": request.build_absolute_uri(f"/orders/paypal/execute/{order.id}/"),
            "cancel_url": request.build_absolute_uri(f"/orders/paypal/cancel/{order.id}/"),
        },
        "transactions": [{
            "amount": {
                "total": total_amount,
                "currency": "USD"
            },
            "description": f"Payment for Order #{order.id} - Rahim Clothing"
        }]
    })

    if payment.create():
        request.session["paypal_payment_id"] = payment.id
        for link in payment.links:
            if link.method == "REDIRECT":
                return redirect(link.href)
    else:
        import json
        print("🚨 PayPal Payment Error:")
        print(json.dumps(payment.error, indent=2))
        messages.error(request, "Unable to create PayPal payment")
        return redirect("orders:order_confirmation", order_id)



def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order.paid = True
    order.save()
    return render(request, "payment_result.html", {"message": "Payment successful", "order": order})


def payment_cancel(request, order_id):
    return render(request, "payment_result.html", {"error": "Payment cancelled"})


@login_required
@require_POST
def save_location(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    order_id = data.get("order_id")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    location_address = data.get("location_address")

    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)

    order.latitude = latitude
    order.longitude = longitude
    if location_address:
        order.location_address = location_address
    order.save()

    return JsonResponse({"status": "success"})


from django.shortcuts import render, redirect, get_object_or_404
from  cart.models import Cart
from orders.forms import OrderForm
from orders.models import Order, OrderItem
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.db import transaction
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
import logging
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from django.http import JsonResponse
from orders.utils import reverse_geocode
from orders.services import assign_warehouses_and_update_stock
from django.utils import timezone
from django.apps import apps
from .models import Transaction, EmailDispatchLog, PaymentEvent

import stripe
import paypalrestsdk
import requests
import json
import hmac
import hashlib
import time
from decimal import Decimal, InvalidOperation

# Configure Stripe and PayPal with keys from settings
stripe.api_key = settings.STRIPE_SECRET_KEY
paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET,
})

# Create your views here.





logger = logging.getLogger(__name__)

_LAST_CALLS: dict[str, float] = {}


def _parse_coord(val):
    try:
        return Decimal(val)
    except (InvalidOperation, TypeError):
        raise


@require_GET
def geo_autocomplete(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 3:
        return JsonResponse({"results": []})

    ip = request.META.get("REMOTE_ADDR", "unknown")
    now = time.time()
    if now - _LAST_CALLS.get(ip, 0) < 0.2:
        return JsonResponse({"results": []})
    _LAST_CALLS[ip] = now

    try:
        r = requests.get(
            "https://api.geoapify.com/v1/geocode/autocomplete",
            params={
                "text": q,
                "limit": 6,
                "format": "json",
                "filter": "countrycode:ke",
                "apiKey": settings.GEOAPIFY_API_KEY,
            },
            timeout=5,
        )
        data = r.json() if r.ok else {"results": []}
        return JsonResponse(data, status=r.status_code if r.ok else 200)
    except requests.RequestException:
        return JsonResponse({"results": []}, status=200)

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
                    try:
                        txt = (request.POST.get("dest_address_text") or "").strip()
                        lat = _parse_coord(request.POST.get("dest_lat"))
                        lng = _parse_coord(request.POST.get("dest_lng"))
                        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                            raise ValueError
                    except Exception:
                        messages.error(request, "Please select a valid delivery address from suggestions.")
                        return redirect("orders:order_create")

                    with transaction.atomic():
                        order = form.save(commit=False)
                        order.user = request.user
                        order.dest_address_text = txt
                        order.dest_lat = lat
                        order.dest_lng = lng
                        order.dest_source = "autocomplete"
                        # Backwards compatibility
                        order.address = txt
                        order.latitude = float(lat)
                        order.longitude = float(lng)
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
        "GEOAPIFY_ENABLED": bool(settings.GEOAPIFY_API_KEY),
    })
    


def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "orders/order_confirmation.html", {"order":order})






def get_location_info(request):
    lat = request.GET.get("lat", "51.21709661403662")
    lon = request.GET.get("lon", "6.7782883744862374")

    data = reverse_geocode(lat, lon)
    return JsonResponse(data)

@require_http_methods(["GET", "POST"])
def paystack_checkout(request, order_id):
    """Initialize a Paystack transaction for card or M-Pesa."""
    order = get_object_or_404(Order, id=order_id)

    # Try to fetch payment method from GET or POST
    payment_method = request.GET.get("payment_method") or request.POST.get("payment_method")
    if payment_method not in {"card", "mpesa"}:
        messages.error(request, "Invalid payment method")
        return redirect("orders:order_confirmation", order.id)

    # Choose Paystack channel
    channel = "card" if payment_method == "card" else "mobile_money"

    # Build email (fallback to user's email)
    payer_email = order.email or (order.user.email if hasattr(order.user, "email") else None)
    if not payer_email:
        messages.error(request, "No valid email found for Paystack checkout.")
        return redirect("orders:order_confirmation", order.id)

    # Prepare Paystack API payload
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    data = {
        "email": payer_email,
        "amount": int(order.get_total_cost()) * 100,
        "callback_url": request.build_absolute_uri(
            reverse("orders:paystack_payment_confirm")
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

        # Fail gracefully if Paystack rejects the request
        if not response.ok or "data" not in res_data:
            print("💥 Paystack Init Failure:", res_data)
            raise Exception("Invalid Paystack response")

        # Extract redirect URL and reference
        auth_url = res_data["data"]["authorization_url"]
        reference = res_data["data"]["reference"]

        # Save transaction with default 'unknown' status
        Transaction.objects.create(
            user=order.user,
            order=order,
            amount=order.get_total_cost(),
            method=payment_method,
            gateway="paystack",
            status="unknown",  # ✅ model now defaults to this
            reference=reference,
            email=payer_email
        )

        return redirect(auth_url)

    except Exception as e:
        print("🔥 Paystack Init Error:", e)
        messages.error(request, "Unable to initialize Paystack payment.")

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
@csrf_exempt
def paystack_webhook(request):
    """Handle Paystack payment notifications with idempotency."""

    logger = logging.getLogger("paystack")

    signature = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")
    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(), request.body, hashlib.sha512
    ).hexdigest()
    if not hmac.compare_digest(signature, computed):
        logger.warning("Invalid Paystack signature")
        return HttpResponse(status=400)

    body = request.body
    event = json.loads(body or b"{}")
    data = event.get("data", {})
    reference = data.get("reference")
    if not reference:
        return HttpResponse(status=400)

    sha = hashlib.sha256(body).hexdigest()
    pe, created = PaymentEvent.objects.get_or_create(
        body_sha256=sha,
        defaults={"provider": "paystack", "reference": reference, "body": event},
    )
    if not created:
        return HttpResponse(status=200)

    event_type = event.get("event")
    order_id = data.get("metadata", {}).get("order_id")
    customer_email = data.get("customer", {}).get("email")

    with transaction.atomic():
        try:
            tx = Transaction.objects.select_for_update().get(reference=reference)
        except Transaction.DoesNotExist:
            logger.error(f"[Webhook] Unknown transaction: {reference}")
            return HttpResponse(status=200)

        if tx.callback_received:
            return HttpResponse(status=200)

        tx.callback_received = True
        tx.raw_event = event
        tx.processed_at = timezone.now()
        if customer_email and not tx.email:
            tx.email = customer_email

        order = None
        if order_id:
            try:
                order = Order.objects.select_for_update().get(id=order_id)
            except Order.DoesNotExist:
                order = None

        if event_type == "charge.success":
            tx.status = "success"
            tx.verified = True
            tx.save(
                update_fields=[
                    "callback_received",
                    "verified",
                    "status",
                    "email",
                    "raw_event",
                    "processed_at",
                ]
            )
            if order:
                order.paid = True
                order.payment_status = "success"
                order.save(update_fields=["paid", "payment_status"])
                assign_warehouses_and_update_stock(order)
        elif event_type == "charge.failed":
            tx.status = "failed"
            tx.save(
                update_fields=[
                    "callback_received",
                    "status",
                    "email",
                    "raw_event",
                    "processed_at",
                ]
            )
            if order:
                order.payment_status = "failed"
                order.save(update_fields=["payment_status"])
        elif event_type == "charge.cancelled":
            tx.status = "cancelled"
            tx.save(
                update_fields=[
                    "callback_received",
                    "status",
                    "email",
                    "raw_event",
                    "processed_at",
                ]
            )
            if order:
                order.payment_status = "cancelled"
                order.save(update_fields=["payment_status"])
        else:
            tx.status = "pending"
            tx.save(
                update_fields=[
                    "callback_received",
                    "status",
                    "email",
                    "raw_event",
                    "processed_at",
                ]
            )

    return HttpResponse(status=200)



def paystack_payment_confirm(request):
    """Redirect from Paystack after user completes checkout.

    The webhook will verify the payment and update records, so this view simply
    redirects to the success page without modifying any state.
    """
    reference = request.GET.get("reference")
    if not reference:
        return render(request, "payment_result.html", {"error": "Missing reference"})

    transaction = get_object_or_404(Transaction, reference=reference, gateway="paystack")
    return redirect("orders:payment_success", transaction.order.id)


def send_payment_receipt_email(transaction, order):
    subject = f"🧾 Payment Receipt for Order #{order.id}"
    recipient = [transaction.email]
    
    message = render_to_string("emails/payment_receipt.html", {
        "user": transaction.user,
        "order": order,
        "transaction": transaction,
    })

    send_mail(
        subject=subject,
        message="This is an HTML email. Please use an HTML-capable client.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient,
        html_message=message,
    )

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
    last_tx = (
        Transaction.objects.filter(order=order)
        .order_by("-created_at")
        .first()
    )

    # Default message for non‐Paystack flows
    message = "Payment successful"

    # If this was a Paystack transaction, we soft-trust until webhook
    if last_tx and last_tx.gateway == "paystack":
        order.payment_status = "pending_confirmation"
        order.paid = False
        order.save(update_fields=["payment_status", "paid"])
        message = "Payment received. Awaiting confirmation."
    else:
        # All other gateways we trust at redirect time
        order.paid = True
        order.payment_status = "paid"
        order.save(update_fields=["paid", "payment_status"])
        if order.payment_method in ["card", "mpesa"]:
            assign_warehouses_and_update_stock(order)

    return render(
        request,
        "payment_result.html",
        {
            "message": message,
            "order": order,
        },
    )





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

    if order.coords_locked:
        return JsonResponse({"status": "locked"})

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    order.latitude = latitude
    order.longitude = longitude
    if location_address:
        order.location_address = location_address
    order.coords_locked = True
    order.coords_source = "browser"
    order.coords_updated_at = timezone.now()
    order.save(update_fields=[
        "latitude",
        "longitude",
        "location_address",
        "coords_locked",
        "coords_source",
        "coords_updated_at",
    ])

    assign_warehouses_and_update_stock(order)

    return JsonResponse({"status": "success"})



@login_required
def track_order(request, order_id: int):
    Order = apps.get_model("orders", "Order")
    Delivery = apps.get_model("orders", "Delivery")
    order = get_object_or_404(Order.objects.select_related("user"), pk=order_id)
    is_owner = order.user_id == request.user.id
    is_vendorish = request.user.is_staff or request.user.groups.filter(name__in=["Vendor", "Vendor Staff"]).exists()
    if not (is_owner or is_vendorish):
        return HttpResponseForbidden("Not allowed")
    delivery = Delivery.objects.filter(order=order).order_by("-id").first()
    warehouse = None
    if delivery and delivery.origin_lat is not None and delivery.origin_lng is not None:
        warehouse = {"lat": float(delivery.origin_lat), "lng": float(delivery.origin_lng)}
    else:
        item = order.items.select_related("warehouse").first()
        wh = getattr(item, "warehouse", None)
        if wh and wh.latitude is not None and wh.longitude is not None:
            warehouse = {"lat": wh.latitude, "lng": wh.longitude}
    route_ctx = {
        "apiKey": settings.GEOAPIFY_API_KEY,
        "warehouse": warehouse,
        "destination": {"lat": float(order.dest_lat), "lng": float(order.dest_lng)},
        "wsUrl": f"/ws/deliveries/{delivery.id}/" if delivery else "",
    }
    route_ctx_json = json.dumps(route_ctx)
    return render(
        request,
        "orders/track.html",
        {
            "order": order,
            "delivery": delivery,
            "ws_path": route_ctx["wsUrl"],
            "route_ctx": route_ctx_json,
        },
    )

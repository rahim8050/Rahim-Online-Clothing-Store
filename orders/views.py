# orders/views.py
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import time
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import paypalrestsdk
import requests
import stripe
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import (
    require_GET,
    require_POST,
    require_http_methods,
)

from cart.models import Cart
from orders.forms import OrderForm
from orders.models import (
    Delivery,
    DeliveryPing,
    EmailDispatchLog,  # kept import if used elsewhere
    Order,
    OrderItem,
    PaymentEvent,
    Transaction,
)
from orders.money import to_minor_units
from orders.services import assign_warehouses_and_update_stock
from orders.services.totals import safe_order_total
from orders.utils import derive_ui_payment_status, reverse_geocode
from payments.gateways import maybe_refund_duplicate_success
from payments.notify import emit_once, send_payment_email, send_refund_email
from payments.serializers import PaystackWebhookSerializer
from users.utils import is_vendor_or_staff

logger = logging.getLogger(__name__)

# ---------- Third-party SDK config ----------
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
paypalrestsdk.configure(
    {
        "mode": getattr(settings, "PAYPAL_MODE", "sandbox"),
        "client_id": getattr(settings, "PAYPAL_CLIENT_ID", ""),
        "client_secret": getattr(settings, "PAYPAL_CLIENT_SECRET", ""),
    }
)

# ---------- Decimal helpers ----------
Q6 = Decimal("0.000001")
Q2 = Decimal("0.01")


def _q6(x) -> Decimal:
    return Decimal(str(x)).quantize(Q6, rounding=ROUND_HALF_UP)


def q2(x) -> Decimal:
    x = x if isinstance(x, Decimal) else Decimal(str(x))
    return x.quantize(Q2, rounding=ROUND_HALF_UP)


def _parse_coord(val):
    return Decimal(str(val))


# ---------- Driver auth ----------
def is_driver(u):
    return u.is_authenticated and u.groups.filter(name__iexact="driver").exists()


driver_required = user_passes_test(is_driver)

# ---------- Simple in-memory route cache (short TTL) ----------
_ROUTE_CACHE: dict[str, tuple[float, dict]] = {}
_ROUTE_TTL = 60  # seconds


def _route_cache_key(a_lat, a_lng, b_lat, b_lng) -> str:
    return f"{round(a_lat,5)},{round(a_lng,5)}:{round(b_lat,5)},{round(b_lng,5)}"


def _cache_get(k: str):
    item = _ROUTE_CACHE.get(k)
    if not item:
        return None
    ts, payload = item
    if time.time() - ts > _route_TTL:
        _ROUTE_CACHE.pop(k, None)
        return None
    return payload


def _cache_set(k: str, payload: dict):
    _ROUTE_CACHE[k] = (time.time(), payload)


def _to_latlng(coords, ref=None):
    """Return coords as [lat, lng]. If ref given, choose orientation closest to ref."""
    if not coords:
        return []
    if ref is not None:
        first = coords[0]
        as_is = _haversine_km(first[0], first[1], ref[0], ref[1])
        flipped = _haversine_km(first[1], first[0], ref[0], ref[1])
        if flipped < as_is:
            return [[c[1], c[0]] for c in coords]
        return [[c[0], c[1]] for c in coords]
    return [[c[1], c[0]] for c in coords]


def _haversine_km(a_lat, a_lng, b_lat, b_lng):
    R = 6371
    dLat = math.radians(b_lat - a_lat)
    dLng = math.radians(b_lng - a_lng)
    s1 = (
        math.sin(dLat / 2) ** 2
        + math.cos(math.radians(a_lat))
        * math.cos(math.radians(b_lat))
        * math.sin(dLng / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(s1))


def _geoapify_route(a_lat, a_lng, b_lat, b_lng, api_key: str):
    url = "https://api.geoapify.com/v1/routing"
    params = {
        "waypoints": f"{a_lat},{a_lng}|{b_lat},{b_lng}",
        "mode": "drive",
        "format": "geojson",
        "apiKey": api_key,
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    j = r.json()
    feat = (j.get("features") or [None])[0]
    if not feat:
        raise ValueError("geoapify: no route")
    coords = feat["geometry"]["coordinates"]
    if isinstance(coords[0][0], (int, float)):  # LineString
        coords_ll = _to_latlng(coords, (a_lat, a_lng))
    else:  # MultiLineString
        flat = [p for part in coords for p in part]
        coords_ll = _to_latlng(flat, (a_lat, a_lng))
    props = feat.get("properties", {})
    dist_km = (props.get("distance", 0) or 0) / 1000.0
    dur_min = (props.get("time", 0) or 0) / 60.0
    return {"coords": coords_ll, "distance_km": dist_km, "duration_min": dur_min}


def _osrm_route(a_lat, a_lng, b_lat, b_lng):
    base = "https://router.project-osrm.org/route/v1/driving"
    url = f"{base}/{a_lng},{a_lat};{b_lng},{b_lat}"
    r = requests.get(
        url, params={"overview": "full", "geometries": "geojson"}, timeout=10
    )
    r.raise_for_status()
    j = r.json()
    route = (j.get("routes") or [None])[0]
    if not route:
        raise ValueError("osrm: no route")
    coords = route["geometry"]["coordinates"]
    coords_ll = _to_latlng(coords, (a_lat, a_lng))
    dist_km = (route.get("distance", 0) or 0) / 1000.0
    dur_min = (route.get("duration", 0) or 0) / 60.0
    return {"coords": coords_ll, "distance_km": dist_km, "duration_min": dur_min}


# ---------- DRIVER: HTML shell ----------
@login_required
@driver_required
def driver_deliveries_page(request):
    return render(request, "orders/driver_deliveries.html")


# ---------- DRIVER: list deliveries ----------
@login_required
@driver_required
@require_GET
def driver_deliveries_api(request):
    qs = (
        Delivery.objects.filter(driver=request.user)
        .select_related("order")
        .order_by("-updated_at")
    )
    data = [
        {
            "id": d.id,
            "order_id": d.order_id,
            "status": d.status,
            # Use canonical destination fields on Order
            "dest_lat": float(d.order.dest_lat) if d.order.dest_lat is not None else None,
            "dest_lng": float(d.order.dest_lng) if d.order.dest_lng is not None else None,
            "last_lat": float(d.last_lat) if d.last_lat is not None else None,
            "last_lng": float(d.last_lng) if d.last_lng is not None else None,
            "last_ping_at": d.last_ping_at.isoformat() if d.last_ping_at else None,
        }
        for d in qs
    ]
    return JsonResponse(data, safe=False)


# ---------- DRIVER: post location ping ----------
@login_required
@driver_required
@require_POST
def driver_location_api(request):
    try:
        body = json.loads(request.body.decode("utf-8"))
        delivery_id = int(body["delivery_id"])
        lat = _q6(body["lat"])
        lng = _q6(body["lng"])
    except Exception:
        return JsonResponse({"error": "invalid payload"}, status=400)

    try:
        d = Delivery.objects.get(pk=delivery_id, driver=request.user)
    except Delivery.DoesNotExist:
        return JsonResponse({"error": "not your delivery"}, status=403)

    d.last_lat = lat
    d.last_lng = lng
    d.last_ping_at = timezone.now()
    if d.status == d.Status.ASSIGNED:
        d.status = d.Status.EN_ROUTE
    d.save(update_fields=["last_lat", "last_lng", "last_ping_at", "status", "updated_at"])
    return JsonResponse({"ok": True, "status": d.status, "ts": d.last_ping_at.isoformat()})


# ---------- DRIVER: action ----------
@login_required
@driver_required
@require_POST
def driver_action_api(request):
    try:
        p = json.loads(request.body.decode("utf-8"))
        delivery_id = int(p["delivery_id"])
        action = p["action"]
    except Exception:
        return JsonResponse({"error": "bad payload"}, status=400)

    try:
        d = Delivery.objects.get(pk=delivery_id, driver=request.user)
    except Delivery.DoesNotExist:
        return JsonResponse({"error": "not your delivery"}, status=403)

    now = timezone.now()
    if action == "picked_up":
        d.status = Delivery.Status.PICKED_UP
        d.picked_up_at = now
        d.save(update_fields=["status", "picked_up_at", "updated_at"])
    elif action == "delivered":
        d.status = Delivery.Status.DELIVERED
        d.delivered_at = now
        if d.dest_lat is not None and d.dest_lng is not None:
            d.last_lat, d.last_lng = d.dest_lat, d.dest_lng
            d.save(
                update_fields=["status", "delivered_at", "last_lat", "last_lng", "updated_at"]
            )
        else:
            d.save(update_fields=["status", "delivered_at", "updated_at"])
    elif action == "cancel":
        d.status = Delivery.Status.CANCELLED
        d.save(update_fields=["status", "updated_at"])
    else:
        return JsonResponse({"error": "unknown action"}, status=400)

    return JsonResponse({"ok": True, "status": d.status, "ts": now.isoformat()})


# ---------- DRIVER: route proxy (Geoapify -> OSRM -> straight line) ----------
@login_required
@driver_required
@require_GET
def driver_route_api(request, delivery_id: int):
    try:
        d = Delivery.objects.get(pk=delivery_id, driver=request.user)
    except Delivery.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    # Determine start point
    if d.last_lat is not None and d.last_lng is not None:
        a_lat, a_lng = float(d.last_lat), float(d.last_lng)
    elif d.origin_lat is not None and d.origin_lng is not None:
        a_lat, a_lng = float(d.origin_lat), float(d.origin_lng)
    else:
        return JsonResponse({"error": "no start position"}, status=400)

    if d.dest_lat is None or d.dest_lng is None:
        return JsonResponse({"error": "no destination"}, status=400)
    b_lat, b_lng = float(d.dest_lat), float(d.dest_lng)

    if _haversine_km(a_lat, a_lng, b_lat, b_lng) < 0.12:  # ~120 m
        coords = [[a_lat, a_lng], [b_lat, b_lng]]
        return JsonResponse({"coords": coords, "distance_km": 0.12, "duration_min": 1})

    key = _route_cache_key(a_lat, a_lng, b_lat, b_lng)
    cached = _cache_get(key)
    if cached:
        return JsonResponse(cached)

    try:
        if getattr(settings, "GEOAPIFY_API_KEY", None):
            payload = _geoapify_route(a_lat, a_lng, b_lat, b_lng, settings.GEOAPIFY_API_KEY)
        else:
            payload = _osrm_route(a_lat, a_lng, b_lat, b_lng)
    except Exception:
        payload = {
            "coords": [[a_lat, a_lng], [b_lat, b_lng]],
            "distance_km": _haversine_km(a_lat, a_lng, b_lat, b_lng),
            "duration_min": None,
        }

    coords = payload.get("coords") or []
    payload["coords"] = _to_latlng(coords, (a_lat, a_lng)) if coords else []
    _cache_set(key, payload)
    return JsonResponse(payload)


# ---------- Geo autocomplete ----------
_LAST_CALLS: dict[str, float] = {}


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
                "apiKey": getattr(settings, "GEOAPIFY_API_KEY", ""),
            },
            timeout=5,
        )
        data = r.json() if r.ok else {"results": []}
        return JsonResponse(data, status=r.status_code if r.ok else 200)
    except requests.RequestException:
        return JsonResponse({"results": []}, status=200)


# ---------- Order create ----------
@require_http_methods(["GET", "POST"])
@login_required
def order_create(request):
    cart = None
    cart_id = request.session.get("cart_id")
    if cart_id:
        try:
            cart = get_object_or_404(Cart, id=cart_id)
        except Exception:
            cart = None

    if not cart or not cart.items.exists():
        messages.warning(request, "Your cart is empty")
        return redirect("cart:cart_detail")

    # Allow GET fallback with ?selected=1,2,3
    if request.method == "GET":
        sel = (request.GET.get("selected") or "").strip()
        if sel:
            ids = [int(p) for p in sel.split(",") if p.strip().isdigit()]
            if ids:
                cart.items.update(is_selected=False)
                cart.items.filter(product_id__in=ids).update(is_selected=True)

        form = OrderForm()
    else:
        # POST
        form = OrderForm(request.POST)
        if form.is_valid():
            try:
                txt = (request.POST.get("dest_address_text") or "").strip()
                lat = _parse_coord(request.POST.get("dest_lat"))
                lng = _parse_coord(request.POST.get("dest_lng"))
                if not (
                    Decimal("-90") <= lat <= Decimal("90")
                    and Decimal("-180") <= lng <= Decimal("180")
                ):
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
                # Legacy fields kept in sync (if still present)
                order.address = txt
                order.latitude = lat
                order.longitude = lng
                order.save()

                # Only selected items; if none selected, take all
                selected = cart.items.filter(is_selected=True)
                if not selected.exists():
                    selected = cart.items.all()

                for item in selected:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        product_version=getattr(item.product, "product_version", 1),
                        price=item.product.price,
                        quantity=item.quantity,
                    )
                # Remove checked-out items
                selected.delete()

                # Clear cart if empty
                if not cart.items.exists():
                    cart.delete()
                    request.session.pop("cart_id", None)

                request.session.pop("cart_count", None)

            messages.success(request, "Order placed successfully!")
            return redirect("orders:order_confirmation", order.id)

        messages.error(request, "Please correct the errors in your order form")

    # Sidebar totals
    cart_items = cart.items.filter(is_selected=True)
    if not cart_items.exists():
        cart_items = cart.items.all()
    selected_total = q2(
        sum((i.product.price * i.quantity for i in cart_items), Decimal("0.00"))
    )

    return render(
        request,
        "orders/order_create.html",
        {
            "form": form,
            "cart": cart,
            "cart_items": cart_items,
            "selected_total": selected_total,
            "error_msg": None,
            "GEOAPIFY_ENABLED": bool(getattr(settings, "GEOAPIFY_API_KEY", "")),
        },
    )


def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    last_tx = Transaction.objects.filter(order=order).order_by("-created_at").first()
    ui_payment_status = derive_ui_payment_status(order, last_tx)
    return render(
        request,
        "orders/order_confirmation.html",
        {"order": order, "ui_payment_status": ui_payment_status},
    )


# ---------- Order edit (unpaid only) ----------
@login_required
@require_http_methods(["GET", "POST"])
def order_edit(request, order_id: int):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"), id=order_id, user=request.user
    )
    if not order.is_editable:
        messages.error(request, "This order can no longer be edited.")
        return redirect("orders:order_confirmation", order.id)

    if request.method == "POST":
        try:
            txt = (request.POST.get("dest_address_text") or order.dest_address_text or "").strip()
            lat = _parse_coord(request.POST.get("dest_lat") or order.dest_lat)
            lng = _parse_coord(request.POST.get("dest_lng") or order.dest_lng)
            if not (
                Decimal("-90") <= lat <= Decimal("90")
                and Decimal("-180") <= lng <= Decimal("180")
            ):
                raise ValueError
        except Exception:
            messages.error(request, "Please select a valid delivery address from suggestions.")
            return redirect("orders:order_edit", order.id)

        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                order.dest_address_text = txt
                order.dest_lat = lat
                order.dest_lng = lng
                order.dest_source = "autocomplete"
                order.address = txt
                order.save()

                items = list(order.items.select_for_update().select_related("product"))
                remaining = 0
                for it in items:
                    remove_flag = request.POST.get(f"remove_{it.id}")
                    qty_raw = request.POST.get(f"quantity_{it.id}")
                    try:
                        qty_val = int(qty_raw) if qty_raw is not None else it.quantity
                    except (TypeError, ValueError):
                        qty_val = it.quantity

                    if remove_flag or qty_val <= 0:
                        it.delete()
                        continue

                    if qty_val != it.quantity:
                        it.quantity = max(1, qty_val)
                        it.save(update_fields=["quantity"])
                    remaining += 1

                if remaining == 0:
                    order.delete()
                    messages.info(
                        request,
                        "Order was emptied and removed. Please create a new order from your cart.",
                    )
                    return redirect("cart:cart_detail")

            messages.success(request, "Order updated.")
            return redirect("orders:order_confirmation", order.id)
        else:
            messages.error(request, "Please correct the errors in your form.")
    else:
        form = OrderForm(instance=order)

    selected_total = safe_order_total(order)
    return render(
        request,
        "orders/order_edit.html",
        {
            "form": form,
            "order": order,
            "order_items": order.items.select_related("product"),
            "selected_total": selected_total,
            "error_msg": None,
            "GEOAPIFY_ENABLED": bool(getattr(settings, "GEOAPIFY_API_KEY", "")),
        },
    )


def get_location_info(request):
    lat = request.GET.get("lat", "51.21709661403662")
    lon = request.GET.get("lon", "6.7782883744862374")
    data = reverse_geocode(lat, lon)
    return JsonResponse(data)


# =========================================================
#                         PAYSTACK
# =========================================================
@login_required
def paystack_checkout(request, order_id: int):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    payer_email = getattr(request.user, "email", None) or "customer@example.com"
    payment_method = "paystack"
    channel = request.GET.get("channel", "card")  # or "mobile_money"

    try:
        total_dec = q2(order.get_total_cost())
        headers = {
            "Authorization": f"Bearer {getattr(settings, 'PAYSTACK_SECRET_KEY', '')}",
            "Content-Type": "application/json",
        }
        data = {
            "email": payer_email,
            "amount": to_minor_units(total_dec),  # int minor units
            "currency": getattr(settings, "PAYSTACK_CURRENCY", "KES"),
            "callback_url": request.build_absolute_uri(
                reverse("orders:paystack_payment_confirm")
            ),
            "metadata": {"order_id": order.id, "payment_method": payment_method},
            "channels": [channel],
        }
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=data,
            headers=headers,
            timeout=30,
        )
        res_data = response.json()
        if not response.ok or "data" not in res_data:
            logger.error("💥 Paystack Init Failure: %s", res_data)
            raise Exception("Invalid Paystack response")

        auth_url = res_data["data"]["authorization_url"]
        reference = res_data["data"]["reference"]

        Transaction.objects.create(
            user=order.user,
            order=order,
            amount=total_dec,  # keep Decimal in DB
            method=payment_method,
            gateway="paystack",
            status="pending",
            reference=reference,
            email=payer_email,
        )
        return redirect(auth_url)
    except Exception:
        logger.exception("🔥 Paystack Init Error")
        messages.error(request, "Unable to initialize Paystack payment.")
        return redirect("orders:order_confirmation", order.id)


@csrf_exempt
def paystack_webhook(request):
    """
    Verified, idempotent Paystack webhook with replay dedupe and notifications.
    """
    logger_ps = logging.getLogger("paystack")

    # 1) Verify signature using raw request body
    raw = request.body  # bytes
    signature = (request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "") or "").strip().lower()
    expected = hmac.new(
        (getattr(settings, "PAYSTACK_SECRET_KEY", "")).encode("utf-8"),
        raw,
        hashlib.sha512,
    ).hexdigest().lower()
    if not signature or not hmac.compare_digest(expected, signature):
        logger_ps.warning("Invalid Paystack signature")
        return JsonResponse({"detail": "invalid signature"}, status=401)

    # 2) Parse JSON strictly
    try:
        event = json.loads(raw.decode("utf-8"))
    except Exception:
        return JsonResponse({"detail": "invalid json"}, status=400)

    # 3) Validate schema
    ser = PaystackWebhookSerializer(data=event)
    if not ser.is_valid():
        return JsonResponse({"detail": "invalid payload", "errors": ser.errors}, status=400)

    data = event.get("data", {}) or {}
    reference = data.get("reference")
    if not reference:
        return JsonResponse({"detail": "missing reference"}, status=400)

    # 4) Idempotency via body SHA256
    sha = hashlib.sha256(raw).hexdigest().lower()
    pe, created = PaymentEvent.objects.get_or_create(
        body_sha256=sha,
        defaults={"provider": "paystack", "reference": reference, "body": event},
    )
    if not created:
        return HttpResponse(status=200)

    event_type = event.get("event")
    order_id = (data.get("metadata") or {}).get("order_id")
    customer_email = (data.get("customer") or {}).get("email")

    # 5) Single-source-of-truth update
    with transaction.atomic():
        try:
            tx = Transaction.objects.select_for_update().get(reference=reference)
        except Transaction.DoesNotExist:
            logger_ps.error(f"[Webhook] Unknown transaction: {reference}")
            return HttpResponse(status=200)

        if tx.callback_received:
            return HttpResponse(status=200)

        tx.callback_received = True
        tx.raw_event = event
        tx.processed_at = timezone.now()
        if customer_email and not getattr(tx, "email", None):
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
            tx.body_sha256 = sha
            tx.save(
                update_fields=[
                    "callback_received",
                    "verified",
                    "status",
                    "email",
                    "raw_event",
                    "processed_at",
                    "body_sha256",
                ]
            )
            if order:
                order.paid = True
                order.payment_status = "success"
                order.save(update_fields=["paid", "payment_status"])
                assign_warehouses_and_update_stock(order)

            if getattr(tx, "email", None):
                emit_once(
                    event_key=f"payment_success:{tx.reference}",
                    user=getattr(tx, "user", None),
                    channel="email",
                    payload={"order_id": order_id, "amount": str(tx.amount)},
                    send_fn=lambda: send_payment_email(
                        tx.email, order_id, tx.amount, tx.reference, "received"
                    ),
                )

            if order_id:
                refunded_refs = maybe_refund_duplicate_success(tx)
                if refunded_refs and getattr(tx, "email", None):
                    for ref in refunded_refs:
                        emit_once(
                            event_key=f"refund_completed:{ref}",
                            user=getattr(tx, "user", None),
                            channel="email",
                            payload={"order_id": order_id, "amount": str(tx.amount)},
                            send_fn=lambda ref=ref: send_refund_email(
                                tx.email, order_id, tx.amount, ref, "completed"
                            ),
                        )

        elif event_type == "charge.failed":
            tx.status = "failed"
            tx.body_sha256 = sha
            tx.save(
                update_fields=[
                    "callback_received",
                    "status",
                    "email",
                    "raw_event",
                    "processed_at",
                    "body_sha256",
                ]
            )
            if order:
                order.payment_status = "failed"
                order.save(update_fields=["payment_status"])

            if getattr(tx, "email", None):
                emit_once(
                    event_key=f"payment_failed:{tx.reference}",
                    user=getattr(tx, "user", None),
                    channel="email",
                    payload={"order_id": order_id, "amount": str(tx.amount)},
                    send_fn=lambda: send_payment_email(
                        tx.email, order_id, tx.amount, tx.reference, "failed"
                    ),
                )

        elif event_type == "charge.cancelled":
            tx.status = "cancelled"
            tx.body_sha256 = sha
            tx.save(
                update_fields=[
                    "callback_received",
                    "status",
                    "email",
                    "raw_event",
                    "processed_at",
                    "body_sha256",
                ]
            )
            if order:
                order.payment_status = "cancelled"
                order.save(update_fields=["payment_status"])

            if getattr(tx, "email", None):
                emit_once(
                    event_key=f"payment_cancelled:{tx.reference}",
                    user=getattr(tx, "user", None),
                    channel="email",
                    payload={"order_id": order_id, "amount": str(tx.amount)},
                    send_fn=lambda: send_payment_email(
                        tx.email, order_id, tx.amount, tx.reference, "cancelled"
                    ),
                )
        else:
            tx.status = "pending"
            tx.body_sha256 = sha
            tx.save(
                update_fields=[
                    "callback_received",
                    "status",
                    "email",
                    "raw_event",
                    "processed_at",
                    "body_sha256",
                ]
            )

    return HttpResponse(status=200)


def paystack_payment_confirm(request):
    """Redirect from Paystack after user completes checkout."""
    reference = request.GET.get("reference")
    if not reference:
        return render(request, "payment_result.html", {"error": "Missing reference"})
    transaction = get_object_or_404(Transaction, reference=reference, gateway="paystack")
    return redirect("orders:payment_success", transaction.order.id)


def send_payment_receipt_email(transaction: Transaction, order: Order):
    subject = f"🧾 Payment Receipt for Order #{order.id}"
    recipient = [transaction.email]
    message = render_to_string(
        "emails/payment_receipt.html", {"user": transaction.user, "order": order, "transaction": transaction}
    )
    from django.core.mail import send_mail

    send_mail(
        subject=subject,
        message="This is an HTML email. Please use an HTML-capable client.",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=recipient,
        html_message=message,
    )


# =========================================================
#                          STRIPE
# =========================================================
@login_required
def stripe_checkout(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    amount_kes = q2(order.get_total_cost())
    unit_amount = int((amount_kes * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": getattr(settings, "STRIPE_CURRENCY", "kes"),
                    "product_data": {"name": f"Order {order.id}"},
                    "unit_amount": unit_amount,
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        metadata={"order_id": str(order.id)},
        success_url=request.build_absolute_uri(
            reverse("orders:stripe_payment_success", args=[order.id])
        )
        + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.build_absolute_uri(reverse("orders:payment_cancel", args=[order.id])),
    )
    return redirect(session.url)


@login_required
def Stripe_payment_success(request, order_id):
    session_id = request.GET.get("session_id")
    if not session_id:
        return render(
            request, "orders/payment_failed.html", {"message": "No session ID provided."}
        )
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        payment_intent = stripe.PaymentIntent.retrieve(session.payment_intent)
    except Exception as e:
        return render(
            request, "orders/payment_failed.html", {"message": f"Stripe error: {str(e)}"}
        )

    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.payment_status = "paid"
    order.paid = True
    order.payment_intent_id = payment_intent.id
    try:
        order.stripe_receipt_url = payment_intent.charges.data[0].receipt_url
    except Exception:
        pass
    order.save()

    return render(
        request,
        "orders/payment_success.html",
        {"order": order, "receipt_url": getattr(order, "stripe_receipt_url", None)},
    )


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    try:
        event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=endpoint_secret)
    except Exception:
        return HttpResponse(status=400)

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = (session.get("metadata") or {}).get("order_id")
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                order.payment_status = "paid"
                order.paid = True
                order.payment_intent_id = session.get("payment_intent")
                order.save(update_fields=["payment_status", "paid", "payment_intent_id"])
            except Order.DoesNotExist:
                pass
    elif event.get("type") == "payment_intent.payment_failed":
        logger.warning("Stripe payment failed")
    elif event.get("type") == "charge.refunded":
        logger.info("Stripe refund processed")
    return HttpResponse(status=200)


# =========================================================
#                           PAYPAL
# =========================================================
@csrf_exempt
def paypal_webhook(request):
    try:
        event = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    if event.get("event_type") == "PAYMENT.CAPTURE.COMPLETED":
        resource = event.get("resource", {}) or {}
        reference = resource.get("id")
        invoice = resource.get("invoice_id")
        Transaction.objects.filter(reference=reference).update(status="success")
        if invoice:
            try:
                order = Order.objects.get(id=invoice)
                order.paid = True
                order.payment_status = "paid"
                order.save(update_fields=["paid", "payment_status"])
            except Order.DoesNotExist:
                pass
    return HttpResponse(status=200)


@login_required
def paypal_checkout(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    currency = getattr(settings, "PAYPAL_CURRENCY", "USD")
    total_amount = str(q2(order.get_total_cost()))

    payment = paypalrestsdk.Payment(
        {
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
            "transactions": [
                {
                    "item_list": {
                        "items": [
                            {
                                "name": f"Order {order.id}",
                                "sku": f"{order.id}",
                                "price": total_amount,
                                "currency": currency,
                                "quantity": 1,
                            }
                        ]
                    },
                    "amount": {"total": total_amount, "currency": currency},
                    "description": f"Payment for Order {order.id}",
                }
            ],
        }
    )
    if payment.create():
        Transaction.objects.create(
            user=order.user,
            order=order,
            amount=Decimal(total_amount),
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


@login_required
def paypal_execute(request, order_id):
    # ensure config is in place (idempotent)
    paypalrestsdk.configure(
        {
            "mode": getattr(settings, "PAYPAL_MODE", "sandbox"),
            "client_id": getattr(settings, "PAYPAL_CLIENT_ID", ""),
            "client_secret": getattr(settings, "PAYPAL_CLIENT_SECRET", ""),
        }
    )

    payment_id = request.session.get("paypal_payment_id")
    payer_id = request.GET.get("PayerID")
    if not payment_id or not payer_id:
        messages.error(request, "Invalid PayPal response")
        return redirect("orders:order_confirmation", order_id)

    payment = paypalrestsdk.Payment.find(payment_id)
    if payment.execute({"payer_id": payer_id}):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        order.paid = True
        order.payment_status = "paid"
        order.save(update_fields=["paid", "payment_status"])
        Transaction.objects.filter(reference=payment_id).update(status="success")
        return redirect("orders:payment_success", order.id)

    messages.error(request, "PayPal payment execution failed")
    return redirect("orders:order_confirmation", order_id)


@login_required
def paypal_payment(request, order_id):
    # Optional secondary flow; normalized to settings currency
    currency = getattr(settings, "PAYPAL_CURRENCY", "USD")
    order = get_object_or_404(Order, id=order_id, user=request.user)
    total_amount = str(q2(order.get_total_cost()))

    payment = paypalrestsdk.Payment(
        {
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
            "transactions": [
                {
                    "amount": {"total": total_amount, "currency": currency},
                    "description": f"Payment for Order #{order.id} - Rahim Clothing",
                }
            ],
        }
    )
    if payment.create():
        request.session["paypal_payment_id"] = payment.id
        for link in payment.links:
            if link.method == "REDIRECT":
                return redirect(link.href)
    else:
        try:
            logger.error("🚨 PayPal Payment Error: %s", json.dumps(payment.error, indent=2))
        except Exception:
            logger.error("🚨 PayPal Payment Error (no details)")

    messages.error(request, "Unable to create PayPal payment")
    return redirect("orders:order_confirmation", order_id)


# =========================================================
#                     Generic payment result
# =========================================================
@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    last_tx = Transaction.objects.filter(order=order).order_by("-created_at").first()

    message = "Payment successful"
    if last_tx and last_tx.gateway == "paystack":
        # UI hint until webhook lands
        order.payment_status = "pending_confirmation"
        order.paid = False
        order.save(update_fields=["payment_status", "paid"])
        message = "Payment received. Awaiting confirmation."
    else:
        order.paid = True
        order.payment_status = "paid"
        order.save(update_fields=["paid", "payment_status"])
        if getattr(order, "payment_method", None) in ["card", "mpesa"]:
            assign_warehouses_and_update_stock(order)

    return render(request, "payment_result.html", {"message": message, "order": order})


@login_required
def payment_cancel(request, order_id):
    return render(request, "payment_result.html", {"error": "Payment cancelled"})


# =========================================================
#                     Save location + tracking
# =========================================================
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

    if getattr(order, "coords_locked", False):
        return JsonResponse({"status": "locked"})

    try:
        latitude = Decimal(str(latitude))
        longitude = Decimal(str(longitude))
    except (TypeError, ValueError, InvalidOperation):
        return JsonResponse({"error": "Invalid coordinates"}, status=400)

    order.latitude = latitude
    order.longitude = longitude
    if location_address:
        order.location_address = location_address
    order.coords_locked = True
    order.coords_source = "browser"
    order.coords_updated_at = timezone.now()
    order.save(
        update_fields=[
            "latitude",
            "longitude",
            "location_address",
            "coords_locked",
            "coords_source",
            "coords_updated_at",
        ]
    )

    assign_warehouses_and_update_stock(order)
    return JsonResponse({"status": "success"})


@login_required
def track_order(request, order_id: int):
    OrderModel = apps.get_model("orders", "Order")
    DeliveryModel = apps.get_model("orders", "Delivery")
    order = get_object_or_404(OrderModel.objects.select_related("user"), pk=order_id)

    is_owner = order.user_id == request.user.id
    if not (is_owner or is_vendor_or_staff(request.user)):
        return HttpResponseForbidden("Not allowed")

    delivery = DeliveryModel.objects.filter(order=order).order_by("-id").first()
    warehouse = None
    if delivery and delivery.origin_lat is not None and delivery.origin_lng is not None:
        warehouse = {"lat": float(delivery.origin_lat), "lng": float(delivery.origin_lng)}
    else:
        item = order.items.select_related("warehouse").first()
        wh = getattr(item, "warehouse", None)
        if wh and wh.latitude is not None and wh.longitude is not None:
            warehouse = {"lat": float(wh.latitude), "lng": float(wh.longitude)}

    dest = None
    if order.dest_lat is not None and order.dest_lng is not None:
        dest = {"lat": float(order.dest_lat), "lng": float(order.dest_lng)}

    route_ctx = {
        "apiKey": getattr(settings, "GEOAPIFY_API_KEY", ""),
        "warehouse": warehouse,
        "destination": dest,
        "wsUrl": f"/ws/delivery/track/{delivery.id}/" if delivery else "",
    }
    return render(
        request,
        "orders/track.html",
        {
            "order": order,
            "delivery": delivery,
            "ws_path": route_ctx["wsUrl"],
            "route_ctx": route_ctx,
        },
    )


# ---------- API: get recent delivery pings (for trail) ----------
@login_required
def delivery_pings_api(request, delivery_id: int):
    DeliveryModel = apps.get_model("orders", "Delivery")
    PingModel = apps.get_model("orders", "DeliveryPing")
    d = get_object_or_404(DeliveryModel.objects.select_related("order"), pk=delivery_id)

    is_owner = d.order.user_id == request.user.id
    if not (is_owner or is_vendor_or_staff(request.user)):
        return HttpResponseForbidden("Not allowed")

    qs = PingModel.objects.filter(delivery=d).order_by("-created_at")
    limit = int(request.GET.get("limit", 200))
    limit = max(10, min(limit, 1000))
    rows = list(qs.values_list("lat", "lng", "created_at")[:limit])
    rows.reverse()  # chronological

    data = {
        "delivery": d.pk,
        "count": len(rows),
        "coords": [[float(lat), float(lng)] for (lat, lng, _ts) in rows],
        "ts": [ts.isoformat() for (_lat, _lng, ts) in rows],
    }
    return JsonResponse(data)

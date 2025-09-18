# users/views.py
from __future__ import annotations

import logging
import re
from typing import Any, Dict

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.sites.shortcuts import get_current_site
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Count, Prefetch, OuterRef, Subquery
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import FormView
from django.contrib.admin.views.decorators import staff_member_required

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .utils import in_groups, is_vendor_or_staff, send_activation_email
from .forms import (
    CustomLoginForm,
    RegisterUserForm,
    UserUpdateForm,
    CustomPasswordChangeForm,
    ResendActivationEmailForm,
)
from .tokens import account_activation_token
from .constants import VENDOR, VENDOR_STAFF, DRIVER
from .models import VendorApplication, VendorStaff

from orders.models import Order, OrderItem, Delivery, Transaction

logger = logging.getLogger(__name__)
User = get_user_model()


# -------------------- Simple dev check --------------------
@login_required
def geoapify_test(request):
    api_key = getattr(settings, "GEOAPIFY_API_KEY", "")
    return render(request, "users/accounts/dev.html", {"GEOAPIFY_API_KEY": api_key})


@login_required
def after_login(request):
    # central place to branch by role later if you want
    return redirect("dashboard")


# -------------------- Orders list (optimized) --------------------
@login_required
def my_orders(request):
    # Latest tx id per order via subquery
    latest_tx_id = Subquery(
        Transaction.objects.filter(order_id=OuterRef("pk"))
        .order_by("-id")
        .values("id")[:1]
    )

    orders_qs = (
        Order.objects.filter(user=request.user)
        .order_by("-created_at")
        .annotate(
            delivery_count=Count("deliveries", distinct=True),
            last_tx_id=latest_tx_id,
        )
        .prefetch_related(
            Prefetch(
                "items",
                queryset=OrderItem.objects.select_related("product", "warehouse"),
            ),
            "deliveries",
        )
    )

    # Evaluate and attach last_tx objects in one extra query
    orders = list(orders_qs)
    tx_ids = [o.last_tx_id for o in orders if o.last_tx_id]
    tx_map = {
        tx.id: tx
        for tx in Transaction.objects.filter(id__in=tx_ids).only(
            "id", "order_id", "callback_received", "created_at", "status"
        )
    }
    for o in orders:
        o.last_tx = tx_map.get(o.last_tx_id)  # preserves template usage

    return render(
        request,
        "users/accounts/my_orders.html",
        {"orders": orders, "WS_ORIGIN": getattr(settings, "WS_ORIGIN", "")},
    )


# -------------------- WebSocket debug push (staff only) --------------------
@staff_member_required
def debug_ws_push(request, delivery_id: int):
    """
    Helper to push a test WS event.
    Query params:
      - type: "position_update" or "status" (default: status)
      - lat, lng (floats) when type=position_update
      - status: e.g. "en_route", "picked_up", "delivered"
    Sends to group: delivery.track.<id> (legacy) and delivery.<id> (current).
    """
    msg_type = (request.GET.get("type") or "status").strip()
    status_val = (request.GET.get("status") or "en_route").strip()
    try:
        lat = float(request.GET.get("lat")) if request.GET.get("lat") is not None else None
        lng = float(request.GET.get("lng")) if request.GET.get("lng") is not None else None
    except Exception:
        lat = lng = None

    layer = get_channel_layer()
    if not layer:
        return HttpResponse("no channel layer", status=503)

    # Legacy consumer group
    try:
        async_to_sync(layer.group_send)(
            f"delivery.track.{int(delivery_id)}",
            {
                "type": "broadcast",
                "payload": (
                    {"type": "position_update", "lat": lat, "lng": lng}
                    if msg_type == "position_update"
                    else {"type": "status", "status": status_val}
                ),
            },
        )
    except Exception:
        pass

    # Current consumer group (example unified event type)
    try:
        payload = (
            {"type": "delivery.event", "kind": "position_update", "lat": lat, "lng": lng}
            if msg_type == "position_update"
            else {"type": "delivery.event", "kind": "status", "status": status_val}
        )
        async_to_sync(layer.group_send)(f"delivery.{int(delivery_id)}", payload)
    except Exception:
        pass

    return JsonResponse({"ok": True, "delivery": int(delivery_id), "type": msg_type})


# -------------------- Auth Views --------------------
class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = "users/accounts/login.html"
    redirect_authenticated_user = True
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        ident = (form.cleaned_data.get("username") or "").strip()
        if "@" in ident and "." in ident:
            ident_type = "email"
        elif re.fullmatch(r"[A-Za-z0-9_.-]+", ident):
            ident_type = "username"
        else:
            ident_type = "unknown"

        self.request.session["auth_identifier"] = ident
        self.request.session["auth_identifier_type"] = ident_type

        # Preserve guest cart id
        cart_id = self.request.session.get("cart_id")
        if cart_id:
            self.request.session["cart_id_backup"] = cart_id

        return super().form_valid(form)

    def get_success_url(self):
        return self.get_redirect_url() or self.success_url


class Logout(LogoutView):
    next_page = "/"


# -------------------- Activation --------------------
def activate(request, uidb64: str, token: str):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        messages.error(request, "Invalid activation link.")
        return render(request, "users/accounts/activation_failed.html", status=400)

    if user.is_active:
        messages.info(request, "Your account is already active. Please sign in.")
        return redirect("users:login")

    if not account_activation_token.check_token(user, token):
        messages.error(request, "This activation link is invalid or has expired. You can request a new one.")
        return render(
            request,
            "users/accounts/activation_failed.html",
            {"email": user.email},
            status=400,
        )

    with transaction.atomic():
        user.is_active = True
        user.save(update_fields=["is_active"])

    backend = (getattr(settings, "AUTHENTICATION_BACKENDS", None) or
               ["django.contrib.auth.backends.ModelBackend"])[0]
    login(request, user, backend=backend)
    messages.success(request, "Your account has been activated. Welcome!")
    return redirect("dashboard")


class ResendActivationView(FormView):
    """
    Resend activation link with a short cooldown.
    """
    template_name = "users/accounts/resend_activation.html"
    form_class = ResendActivationEmailForm
    success_url = reverse_lazy("users:resend_activation")
    COOLDOWN_SECONDS = 60  # adjust

    def form_valid(self, form):
        email = form.cleaned_data.get("email", "").strip().lower()
        cache_key = f"resend_activation:{email}"
        if cache.get(cache_key):
            messages.info(
                self.request,
                "We recently sent a link. Check your inbox (and spam) or try again in a few minutes.",
            )
            return redirect(self.success_url)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            messages.error(self.request, "No account found with that email.")
            return redirect(self.success_url)

        if user.is_active:
            messages.info(self.request, "This account is already active.")
            return redirect(self.success_url)

        try:
            send_activation_email(self.request, user)
        except Exception:
            messages.error(self.request, "We couldn’t send the email right now. Please try again shortly.")
            return redirect(self.success_url)

        cache.set(cache_key, True, timeout=self.COOLDOWN_SECONDS)
        messages.success(self.request, "A new activation link has been sent to your email.")
        return redirect(self.success_url)


# -------------------- Profile --------------------
@login_required
def profile_view(request):
    if request.method == "POST":
        if "update_profile" in request.POST:
            profile_form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
            password_form = CustomPasswordChangeForm(user=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Your profile has been updated successfully.")
                return redirect("users:profile")
            messages.error(request, "Please correct the errors in your profile form.")
        elif "change_password" in request.POST:
            password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
            profile_form = UserUpdateForm(instance=request.user)
            if password_form.is_valid():
                user = password_form.save()
                # keep session
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, "Your password was updated successfully.")
                return redirect("users:profile")
            messages.error(request, "Please correct the errors in your password form.")
    else:
        profile_form = UserUpdateForm(instance=request.user)
        password_form = CustomPasswordChangeForm(user=request.user)

    return render(
        request,
        "users/accounts/profile.html",
        {"profile_form": profile_form, "password_form": password_form},
    )


@login_required
def profile_settings_view(request):
    if request.method == "POST":
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect("users:profile_settings")
        messages.error(request, "Please correct the errors in your profile form.")
    else:
        form = UserUpdateForm(instance=request.user)

    return render(request, "users/accounts/profile_settings.html", {"profile_form": form})


# -------------------- Driver pages --------------------
def _is_driver(u) -> bool:
    return in_groups(u, DRIVER)


@login_required
def driver_dashboard(request):
    if not _is_driver(request.user):
        return HttpResponseForbidden("Driver access only")

    DeliveryModel = apps.get_model("orders", "Delivery")
    deliveries = (
        DeliveryModel.objects.filter(driver=request.user)
        .select_related("order")
        .order_by("-id")
    )
    return render(request, "dash/driver.html", {"deliveries": deliveries})


@login_required
def driver_sim(request):
    """
    Simple page to simulate driver movement.
    If ?delivery=<id> is provided, prefill from DB.
    """
    ctx: Dict[str, Any] = {}
    delivery_id = request.GET.get("delivery")
    if delivery_id:
        d = get_object_or_404(Delivery, pk=delivery_id)
        if getattr(d, "warehouse", None):
            ctx["start_lat"] = d.warehouse.latitude
            ctx["start_lng"] = d.warehouse.longitude
        if getattr(d, "order", None):
            ctx["dest_lat"] = getattr(d.order, "latitude", None)
            ctx["dest_lng"] = getattr(d.order, "longitude", None)
        ctx["delivery_id"] = d.id
    return render(request, "users/accounts/driver_sim.html", ctx)


@login_required
def driver_live(request, delivery_id: int):
    # TODO: enforce driver ownership if you have roles
    d = Delivery.objects.select_related("order").get(pk=delivery_id)
    ctx = {
        "delivery_id": d.id,
        "start_lat": getattr(d, "last_lat", None)
        or getattr(getattr(d, "warehouse", None), "latitude", None),
        "start_lng": getattr(d, "last_lng", None)
        or getattr(getattr(d, "warehouse", None), "longitude", None),
    }
    return render(request, "users/accounts/driver_live.html", ctx)


# --- Deprecated: /users/vendor-applications/ -> /apis/vendor/apply/
def vendor_apply_deprecated(request):
    """
    Redirect to the new endpoint. Preserve method for non-GET via 307.
    """
    url = "/apis/vendor/apply/"
    if request.method == "GET":
        resp = HttpResponseRedirect(url)
    else:
        resp = HttpResponseRedirect(url)
        resp.status_code = 307
    resp["Deprecation"] = "true"
    resp["Link"] = f"<{url}>; rel=\"successor-version\""
    return resp

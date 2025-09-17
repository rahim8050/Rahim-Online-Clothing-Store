# users/views.py
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import transaction
from django.db.models import Count, OuterRef, Subquery, Q
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.timezone import now
from django.views import View
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError

from orders.models import Order, Delivery, Transaction  # direct references used in several views
from product_app.utils import get_vendor_field
from users.constants import DRIVER, VENDOR
from users.forms import (
    CustomLoginForm,
    CustomPasswordChangeForm,
    RegisterUserForm,
    ResendActivationEmailForm,
    UserUpdateForm,
)
from users.models import VendorApplication, VendorStaff
from users.serializers import VendorApplicationCreateSerializer, VendorApplicationSerializer
from users.tokens import account_activation_token
from users.utils import in_groups, is_vendor_or_staff, send_activation_email

logger = logging.getLogger(__name__)
User = get_user_model()


# -------------------- Small helpers --------------------
def _is_vendor(u) -> bool:
    return is_vendor_or_staff(u)


def _is_driver(u) -> bool:
    return in_groups(u, DRIVER)


# -------------------- Dev/Diagnostics --------------------
@login_required
def geoapify_test(request):
    api_key = getattr(settings, "GEOAPIFY_API_KEY", "")
    return render(request, "users/accounts/dev.html", {"GEOAPIFY_API_KEY": api_key})


@login_required
def debug_ws_push(request, delivery_id: int):
    """
    Staff-only helper to push a test WS event to a delivery tracking group.
    Accepts optional query params:
      - type: "position_update" or "status" (default: status)
      - lat, lng: numbers when type=position_update
      - status: e.g. "en_route", "picked_up", "delivered"
    Sends to both legacy (delivery.track.<id>) and current (delivery.<id>) groups.
    """
    if not request.user.is_staff:
        return HttpResponseForbidden("staff only")

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

    # Current consumer group
    try:
        payload = (
            {"type": "delivery.event", "kind": "position_update", "lat": lat, "lng": lng}
            if msg_type == "position_update"
            else {"type": "delivery.event", "kind": "status", "status": status_val}
        )
        async_to_sync(layer.group_send)(f"delivery.{int(delivery_id)}", payload)
    except Exception:
        pass

    return HttpResponse("ok")


# -------------------- Orders list (optimized) --------------------
@login_required
def my_orders(request):
    # Latest transaction id per order via subquery
    latest_tx_id = Subquery(
        Transaction.objects.filter(order_id=OuterRef("pk")).order_by("-id").values("id")[:1]
    )

    orders_qs = (
        Order.objects.filter(user=request.user)
        .order_by("-created_at")
        .annotate(delivery_count=Count("deliveries", distinct=True), last_tx_id=latest_tx_id)
    )

    orders = list(orders_qs)
    tx_ids = [o.last_tx_id for o in orders if o.last_tx_id]
    tx_map = {
        tx.id: tx
        for tx in Transaction.objects.filter(id__in=tx_ids).only(
            "id", "order_id", "callback_received", "created_at", "status"
        )
    }
    for o in orders:
        o.last_tx = tx_map.get(o.last_tx_id)

    return render(
        request,
        "users/accounts/my_orders.html",
        {"orders": orders, "WS_ORIGIN": getattr(settings, "WS_ORIGIN", "")},
    )


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
        elif re.fullmatch(r"[A-Za-z0-9_.-]+", ident or ""):
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


# -------------------- Registration / Activation --------------------
class RegisterUser(View):
    template_name = "users/accounts/register.html"
    success_url = reverse_lazy("index")

    def get(self, request):
        return render(request, self.template_name, {"form": RegisterUserForm()})

    def post(self, request):
        form = RegisterUserForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        user = form.save(commit=False)
        user.is_active = False
        user.save()
        send_activation_email(request, user)
        messages.success(
            request,
            "Account created successfully. Check your email to activate your account.",
        )
        return redirect(self.success_url)


def activate(request, uidb64, token):
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
        messages.error(
            request, "This activation link is invalid or has expired. You can request a new one."
        )
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


class ResendActivationEmailView(View):
    template_name = "users/accounts/resend_activation.html"
    COOLDOWN_SECONDS = 300  # 5 minutes

    def get(self, request):
        return render(request, self.template_name, {"form": ResendActivationEmailForm()})

    def post(self, request):
        form = ResendActivationEmailForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        email = (form.cleaned_data["email"] or "").strip()
        cache_key = f"resend_activation:{email.lower()}"

        if cache.get(cache_key):
            messages.info(
                request,
                "We recently sent a link. Check your inbox (and spam) or try again in a few minutes.",
            )
            return redirect("users:resend_activation")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with that email.")
            return redirect("users:resend_activation")

        if user.is_active:
            messages.info(request, "This account is already active.")
            return redirect("users:resend_activation")

        try:
            send_activation_email(request, user)
        except Exception:
            messages.error(request, "We couldn’t send the email right now. Please try again shortly.")
            return redirect("users:resend_activation")

        cache.set(cache_key, True, timeout=self.COOLDOWN_SECONDS)
        messages.success(request, "A new activation link has been sent to your email.")
        return redirect("users:resend_activation")


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


@login_required
def change_password_view(request):
    if request.method == "POST":
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was updated successfully.")
            return redirect("users:change_password")
        messages.error(request, "Please correct the errors in your password form.")
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(request, "users/accounts/change_password.html", {"password_form": form})


# -------------------- Post-login routing --------------------
@login_required
def after_login(request):
    u = request.user
    if _is_vendor(u):
        return redirect("vendor_dashboard")
    if _is_driver(u):
        return redirect("driver_dashboard")

    # Customer dashboard context
    def _current_vendor_app_status(user):
        if not getattr(user, "is_authenticated", False):
            return "none"
        if VendorApplication.objects.filter(user=user, status=VendorApplication.PENDING).exists():
            return "pending"
        last = VendorApplication.objects.filter(user=user).order_by("-created_at").first()
        return (last and last.status) or "none"

    user_is_vendor = u.groups.filter(name="Vendor").exists()
    user_is_vendor_staff = VendorStaff.objects.filter(staff=u, is_active=True).exists()
    ctx = {
        "user_is_vendor": user_is_vendor,
        "user_is_vendor_staff": user_is_vendor_staff,
        "vendor_app_status": _current_vendor_app_status(u),
    }
    return render(request, "dash/customer.html", ctx)


# -------------------- Vendor application APIs --------------------
class VendorApplyAPI(generics.CreateAPIView):
    serializer_class = VendorApplicationCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class VendorApplicationApproveAPI(generics.UpdateAPIView):
    """
    PATCH /users/vendor-applications/{id}/approve/
    body: {"status": "approved" | "rejected"}
    """
    serializer_class = VendorApplicationSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = VendorApplication.objects.all()

    def perform_update(self, serializer):
        status_new = self.request.data.get("status")
        if status_new not in (VendorApplication.APPROVED, VendorApplication.REJECTED):
            raise ValidationError({"status": "Must be approved or rejected"})
        app = serializer.save(status=status_new, decided_by=self.request.user, decided_at=now())
        if status_new == VendorApplication.APPROVED:
            g_vendor, _ = Group.objects.get_or_create(name=VENDOR)
            app.user.groups.add(g_vendor)
            VendorStaff.objects.get_or_create(owner=app.user, staff=app.user, defaults={"is_active": True})


# -------------------- Dashboards --------------------
@login_required
def vendor_dashboard(request):
    u = request.user
    if not _is_vendor(u):
        return HttpResponseForbidden()

    Product = apps.get_model("product_app", "Product")
    DeliveryModel = apps.get_model("orders", "Delivery")

    # Resolve vendor/owner field on Product
    try:
        field = get_vendor_field(Product)  # e.g. "vendor" or "owner"
    except Exception as e:
        logger.warning("Could not resolve vendor field on Product: %s", e)
        field = None

    # Vendor's products
    if field:
        try:
            products = (
                Product.objects.filter(**{field: u})
                .only("id", "name", "price", "available")
                .order_by("-id")[:100]
            )
        except FieldError:
            logger.warning("Product model missing vendor field '%s'", field)
            products = Product.objects.none()
    else:
        products = Product.objects.none()

    # Vendor deliveries
    deliveries = []
    totals = {"all": 0, "pending": 0, "assigned": 0, "en_route": 0, "delivered": 0}
    if DeliveryModel and field:
        vendor_filter = {f"order__items__product__{field}": u}
        base_qs = (
            DeliveryModel.objects.filter(**vendor_filter)
            .select_related("order", "driver")
            .distinct()
            .order_by("-id")
        )
        status_arg = (request.GET.get("status") or "all").strip().lower()
        allowed = {"all", "pending", "assigned", "picked_up", "en_route", "delivered", "cancelled"}
        if status_arg not in allowed:
            status_arg = "all"
        deliveries = base_qs if status_arg == "all" else base_qs.filter(status=status_arg)
        totals = base_qs.aggregate(
            all=Count("id"),
            pending=Count("id", filter=Q(status="pending")),
            assigned=Count("id", filter=Q(status="assigned")),
            en_route=Count("id", filter=Q(status__in=["picked_up", "en_route"])),
            delivered=Count("id", filter=Q(status="delivered")),
        )

    return render(
        request,
        "dash/vendor.html",
        {"products": products, "deliveries": deliveries, "status": request.GET.get("status", "all"), "totals": totals},
    )


@login_required
def driver_dashboard(request):
    u = request.user
    if not _is_driver(u):
        return HttpResponseForbidden()
    deliveries = Delivery.objects.filter(driver=u).select_related("order")
    return render(request, "dash/driver.html", {"deliveries": deliveries})


# -------------------- Driver helpers / simulators --------------------
@login_required
def driver_sim(request):
    """Small helper page to simulate positions; prefill via ?delivery=<id>."""
    ctx: Dict[str, Any] = {}
    delivery_id = request.GET.get("delivery")
    if delivery_id:
        d = get_object_or_404(Delivery.objects.select_related("order"), pk=delivery_id)
        # Prefer Delivery origin snapshot; fallback to first item warehouse
        if d.origin_lat is not None and d.origin_lng is not None:
            ctx["start_lat"] = float(d.origin_lat)
            ctx["start_lng"] = float(d.origin_lng)
        else:
            it = d.order.items.select_related("warehouse").first()
            wh = getattr(it, "warehouse", None)
            if wh and wh.latitude is not None and wh.longitude is not None:
                ctx["start_lat"] = float(wh.latitude)
                ctx["start_lng"] = float(wh.longitude)
        if d.order.dest_lat is not None and d.order.dest_lng is not None:
            ctx["dest_lat"] = float(d.order.dest_lat)
            ctx["dest_lng"] = float(d.order.dest_lng)
        ctx["delivery_id"] = d.id
    return render(request, "users/accounts/driver_sim.html", ctx)


@login_required
def driver_live(request, delivery_id: int):
    d = get_object_or_404(Delivery.objects.select_related("order"), pk=delivery_id)
    ctx = {
        "delivery_id": d.id,
        "start_lat": float(d.last_lat) if d.last_lat is not None else None,
        "start_lng": float(d.last_lng) if d.last_lng is not None else None,
    }
    return render(request, "users/accounts/driver_live.html", ctx)


# --- Deprecated: /users/vendor-applications/ -> /apis/vendor/apply/
def vendor_apply_deprecated(request):
    resp = HttpResponseRedirect("/apis/vendor/apply/")
    resp["Deprecation"] = "true"
    resp["Link"] = '</apis/vendor/apply/>; rel="successor-version"'
    if request.method != "GET":
        resp.status_code = 307  # preserve method
    return resp

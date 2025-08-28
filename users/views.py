# users/views.py
from __future__ import annotations
from .utils import send_activation_email, is_vendor_or_staff, in_groups
import logging
import re
from django.core.cache import cache
from django.db import transaction
from django.core.exceptions import ImproperlyConfigured
from django.views.generic import FormView
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import FieldError
from django.core.mail import EmailMessage
from django.db.models import Q, Count
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.generic import FormView, View
from rest_framework import generics, permissions
from django.utils.timezone import now
from django.contrib.auth.models import Group
from rest_framework.exceptions import ValidationError

from orders.models import Order
from product_app.utils import get_vendor_field
from .forms import (
    CustomLoginForm,
    RegisterUserForm,
    UserUpdateForm,
    CustomPasswordChangeForm,
    ResendActivationEmailForm,
)
from .constants import VENDOR, VENDOR_STAFF, DRIVER
from .tokens import account_activation_token
from .models import VendorApplication, VendorStaff
from .serializers import VendorApplicationCreateSerializer, VendorApplicationSerializer

User = get_user_model()
logger = logging.getLogger(__name__)
from orders.models import Order
@login_required
def geoapify_test(request):
    # Show the key if set; don't crash if missing
    api_key = getattr(settings, "GEOAPIFY_API_KEY", "")
    return render(request, "users/accounts/dev.html", {
        "GEOAPIFY_API_KEY": api_key,
    })
@login_required
def my_orders(request):
    orders = (
        Order.objects
        .filter(user=request.user)
        .order_by('-created_at')
        .prefetch_related('items__product', 'items__warehouse', 'deliveries')
        .annotate(delivery_count=Count('deliveries'))
    )

    # Attach last transaction per order (used by template to show verified status)
    for o in orders:
        o.last_tx = o.transaction_set.order_by('-id').first()

    return render(
        request,
        'users/accounts/my_orders.html',
        {'orders': orders},
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


# -------------------- Registration / Profile --------------------


class RegisterUser(FormView):
    template_name = "users/accounts/register.html"
    success_url = reverse_lazy("index")

    # ✅ avoids circular import / NoneType in FormView.get_form()
    def get_form_class(self):
        try:
            return RegisterUserForm
        except Exception as e:
            raise ImproperlyConfigured(f"Cannot import RegisterUserForm: {e}")

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False
        user.save()
        send_activation_email(self.request, user)  # HTML + text, raises on failure
        messages.success(self.request, "Account created successfully. Check your email to activate your account.")
        return redirect(self.get_success_url())




def activate(request, uidb64, token):
    # Resolve user or fail cleanly
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
        return render(request, "users/accounts/activation_failed.html", {"email": user.email}, status=400)

    with transaction.atomic():                               # ✅ atomic activate
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
            messages.info(request, "We recently sent a link. Check your inbox (and spam) or try again in a few minutes.")
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


# -------------------- Split Profile Pages --------------------
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

    return render(
        request,
        "users/accounts/profile_settings.html",
        {"profile_form": form},
    )


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

    return render(
        request,
        "users/accounts/change_password.html",
        {"password_form": form},
    )


# -------------------- Dashboards --------------------

def _is_vendor(u):  # small helpers for readability
    return is_vendor_or_staff(u)

def _is_driver(u):
    return in_groups(u, DRIVER)

@login_required
def after_login(request):
    u = request.user
    if _is_vendor(u):
        return redirect("vendor_dashboard")
    if _is_driver(u):
        return redirect("driver_dashboard")
    return render(request, "dash/customer.html")


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


@login_required
def vendor_dashboard(request):
    u = request.user
    if not _is_vendor(u):
        return HttpResponseForbidden()

    Product = apps.get_model("product_app", "Product")
    Delivery = apps.get_model("orders", "Delivery")  # may be None

    # Resolve vendor/owner field on Product
    try:
        field = get_vendor_field(Product)
    except Exception as e:
        logger.warning("Could not resolve vendor field on Product: %s", e)
        field = None

    # Vendor's own products (safe even if field is None)
    if field:
        try:
            products = (Product.objects
                        .filter(**{field: u})
                        .only("id", "name", "price", "available")
                        .order_by("-id")[:100])
        except FieldError:
            logger.warning("Product model missing vendor field '%s'", field)
            products = Product.objects.none()
    else:
        products = Product.objects.none()

    # Vendor deliveries (guard if Delivery model missing)
    deliveries = []
    totals = {"all": 0, "pending": 0, "assigned": 0, "en_route": 0, "delivered": 0}
    if Delivery:
        vendor_filter = {f"order__items__product__{field}": u} if field else {}
        base_qs = (Delivery.objects
                   .filter(**vendor_filter)
                   .select_related("order", "driver")
                   .distinct()
                   .order_by("-id"))
        status = (request.GET.get("status") or "all").strip().lower()
        allowed = {"all", "pending", "assigned", "picked_up", "en_route", "delivered", "cancelled"}
        if status not in allowed:
            status = "all"
        deliveries = base_qs if status == "all" else base_qs.filter(status=status)
        totals = base_qs.aggregate(
            all=Count("id"),
            pending=Count("id", filter=Q(status="pending")),
            assigned=Count("id", filter=Q(status="assigned")),
            en_route=Count("id", filter=Q(status__in=["picked_up", "en_route"])),
            delivered=Count("id", filter=Q(status="delivered")),
        )

    return render(
        request,
        "dash/vendor.html",   # ✅ use your templates/dash/vendor.html
        {"products": products, "deliveries": deliveries, "status": request.GET.get("status", "all"), "totals": totals},
    )


@login_required
def driver_dashboard(request):
    u = request.user
    if not _is_driver(u):
        return HttpResponseForbidden()

    Delivery = apps.get_model("orders", "Delivery")
    deliveries = Delivery.objects.filter(driver=u).select_related("order") if Delivery else []

    return render(request, "dash/driver.html", {"deliveries": deliveries})

from django.shortcuts import render, get_object_or_404
from orders.models import Delivery
def driver_sim(request):
    ctx = {}
    # If you pass ?delivery=16 in the URL, prefill from DB
    delivery_id = request.GET.get("delivery")
    if delivery_id:
        d = get_object_or_404(Delivery, pk=delivery_id)
        # Example fields—adapt to your model
        if getattr(d, "warehouse", None):
            ctx["start_lat"] = d.warehouse.latitude
            ctx["start_lng"] = d.warehouse.longitude
        if getattr(d, "order", None):
            ctx["dest_lat"] = getattr(d.order, "latitude", None)
            ctx["dest_lng"] = getattr(d.order, "longitude", None)
        ctx["delivery_id"] = d.id
    return render(request, "users/accounts/driver_sim.html", ctx)





from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.apps import apps

Delivery = apps.get_model('orders', 'Delivery')  # adjust app label if different

@login_required
def driver_live(request, delivery_id: int):
    # TODO: enforce driver role/ownership if you have roles
    d = Delivery.objects.select_related("order").get(pk=delivery_id)
    ctx = {
        "delivery_id": d.id,
        "start_lat": getattr(d, "last_lat", None) or getattr(getattr(d, "warehouse", None), "latitude", None),
        "start_lng": getattr(d, "last_lng", None) or getattr(getattr(d, "warehouse", None), "longitude", None),
    }
    return render(request, "users/accoonts/driver_live.html", ctx)

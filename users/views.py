# users/views.py
from __future__ import annotations

import logging
import re
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

from orders.models import Order
from product_app.utils import get_vendor_field
from .forms import (
    CustomLoginForm,
    RegisterUserForm,
    UserUpdateForm,
    CustomPasswordChangeForm,
    ResendActivationEmailForm,
)
from .roles import ROLE_VENDOR, ROLE_VENDOR_STAFF, ROLE_DRIVER
from .tokens import account_activation_token

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
    orders = Order.objects.filter(user=request.user).order_by('-created_at')

    # Attach last transaction per order (optional, keeps your template simple)
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
    form_class = RegisterUserForm
    success_url = reverse_lazy("index")

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False
        user.save()

        current_site = get_current_site(self.request)
        mail_subject = "Activate your account"
        message = render_to_string(
            "users/accounts/acc_activate_email.html",
            {
                "user": user,
                "domain": current_site.domain,
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": account_activation_token.make_token(user),
                "protocol": "https" if self.request.is_secure() else "http",
            },
        )

        email = EmailMessage(mail_subject, message, to=[user.email])
        email.content_subtype = "html"
        email.send()

        messages.success(
            self.request,
            "Account created successfully. Please check your email to activate your account.",
        )
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)


def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return render(request, "users/accounts/activation_success.html")
    return render(request, "users/accounts/activation_failed.html")


class ResendActivationEmailView(View):
    template_name = "users/accounts/resend_activation.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ResendActivationEmailForm()})

    def post(self, request):
        form = ResendActivationEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                user = User.objects.get(email=email)
                if user.is_active:
                    messages.info(request, "This account is already active.")
                else:
                    current_site = get_current_site(request)
                    mail_subject = "Activate your account"
                    message = render_to_string(
                        "users/accounts/acc_activate_email.html",
                        {
                            "user": user,
                            "domain": current_site.domain,
                            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                            "token": account_activation_token.make_token(user),
                        },
                    )
                    EmailMessage(mail_subject, message, to=[user.email]).send()
                    messages.success(request, "A new activation link has been sent to your email.")
            except User.DoesNotExist:
                messages.error(request, "No account found with that email.")
            return redirect("users:resend_activation")
        return render(request, self.template_name, {"form": form})


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


# -------------------- Dashboards --------------------

def _is_vendor(u):  # small helpers for readability
    return u.groups.filter(name__in=[ROLE_VENDOR, ROLE_VENDOR_STAFF]).exists() or u.is_staff

def _is_driver(u):
    return u.groups.filter(name=ROLE_DRIVER).exists()

@login_required
def after_login(request):
    u = request.user
    if _is_vendor(u):
        return redirect("vendor_dashboard")
    if _is_driver(u):
        return redirect("driver_dashboard")
    return render(request, "dash/customer.html")


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

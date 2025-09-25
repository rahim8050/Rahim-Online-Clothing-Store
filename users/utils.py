# users/utils.py
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode
from rest_framework.exceptions import PermissionDenied

from core.siteutils import absolute_url

from .constants import VENDOR, VENDOR_STAFF
from .tokens import account_activation_token

logger = logging.getLogger(__name__)
User = get_user_model()


# ----------------------------
# Group / role helpers
# ----------------------------
def in_groups(user, *groups: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return user.is_superuser or user.groups.filter(name__in=groups).exists()


def is_vendor_or_staff(user) -> bool:
    return in_groups(user, VENDOR, VENDOR_STAFF) or getattr(user, "is_staff", False)


def get_active_vendor_staff(user):
    """Return active VendorStaff rows where this user is staff."""
    from .models import VendorStaff

    return VendorStaff.objects.filter(staff=user, is_active=True)


# ----------------------------
# Owner resolution (fixed)
# ----------------------------
def vendor_owner_ids_for(user) -> set[int]:
    """
    Return a *set* of owner User IDs that this user can act for:
      - the user's own id if they are in the Vendor group
      - any owners where the user is active staff (VendorStaff.is_active=True)
    """
    owner_ids: set[int] = set()

    # If the user is a Vendor owner, they can act as themselves.
    if user.groups.filter(name=VENDOR).exists() or user.is_superuser:
        owner_ids.add(user.id)

    # If the user is active staff, include those owners.
    from .models import VendorStaff

    staff_owner_ids = VendorStaff.objects.filter(
        staff=user, is_active=True
    ).values_list("owner_id", flat=True)

    owner_ids.update(staff_owner_ids)
    return owner_ids


def resolve_vendor_owner_for(
    user,
    owner_id: int | None = None,
    *,
    require_explicit_if_multiple: bool = True,
) -> int:
    """
    Decide which vendor owner id to act for.

    Behavior:
    - If owner_id is provided:
        * must be int and inside allowed set -> return it
        * else -> raise PermissionDenied (403)
    - If owner_id is None:
        * 0 allowed -> PermissionDenied (403)
        * 1 allowed -> auto-pick that id
        * >1 allowed -> ValueError (400 at serializer) unless you set require_explicit_if_multiple=False
    """
    allowed = vendor_owner_ids_for(user)

    if owner_id is not None:
        # Validate type
        try:
            oid = int(owner_id)
        except (TypeError, ValueError):
            # Malformed input -> your serializer should convert this to a 400 field error
            raise ValueError("owner_id must be an integer or null.")
        # Authorization
        if oid in allowed:
            return oid
        raise PermissionDenied("Not authorized to act for that vendor owner.")

    # owner_id omitted/null -> infer
    if not allowed:
        raise PermissionDenied("You do not have any vendor owner context.")
    if len(allowed) == 1:
        return next(iter(allowed))
    if require_explicit_if_multiple:
        # Ambiguous but valid -> serializer should surface as 400 on owner_id field
        raise ValueError("Multiple vendor owners found; specify owner_id.")
    # Deterministic fallback if you ever want auto-pick:
    return sorted(allowed)[0]


# ----------------------------
# Email (unchanged)
# ----------------------------
def send_activation_email(request, user) -> None:
    """
    Renders and sends the activation email (HTML + text).
    Uses DEFAULT_FROM_EMAIL as sender (explicit).
    """
    try:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        activation_path = reverse(
            "users:activate", kwargs={"uidb64": uid, "token": token}
        )
        activation_url = absolute_url(activation_path, request=request)
        support_email = getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL)
        site_name = getattr(settings, "SITE_NAME", "Rahim Online Shop")

        ctx = {
            "user": user,
            "uid": uid,
            "token": token,
            "activation_url": activation_url,
            "support_email": support_email,
            "site_name": site_name,
        }

        subject = "Activate your account"
        html_body = render_to_string(
            "users/accounts/acc_activate_email.html", ctx, request=request
        )
        text_body = strip_tags(html_body)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            headers={"X-Transactional": "account-activation"},
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:
        logger.error(
            "Failed to send activation email to %s: %s",
            user.email,
            e,
            exc_info=True,
        )
        raise

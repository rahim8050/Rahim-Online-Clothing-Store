# users/utils.py
from __future__ import annotations
import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode

from .constants import VENDOR, VENDOR_STAFF
from .tokens import account_activation_token

logger = logging.getLogger(__name__)
User = get_user_model()


def in_groups(user, *groups: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return user.groups.filter(name__in=groups).exists() or user.is_superuser


def is_vendor_or_staff(user) -> bool:
    return in_groups(user, VENDOR, VENDOR_STAFF) or getattr(user, "is_staff", False)


def vendor_owner_ids_for(user):
    """
    Returns the set of owner User IDs that this user acts for:
    - self if in Vendor group
    - any owners where user is active staff
    """
    return User.objects.filter(
        Q(pk=user.pk, groups__name=VENDOR)
        | Q(vendor_staff_owned__staff=user, vendor_staff_owned__is_active=True)
        | Q(
            vendor_staff_memberships__owner__groups__name=VENDOR,
            vendor_staff_memberships__is_active=True,
        )
    ).values_list("id", flat=True).distinct()


def resolve_vendor_owner_for(user, owner_id: Optional[int] = None) -> int:
    """
    Decide the vendor owner id to use when creating a Product.
    - If owner_id is provided, verify authorization and return it.
    - If not:
        * return self if user is vendor and has no other owners
        * return the single owner if staff of exactly one owner
        * else raise for explicit selection
    """
    ids_qs = vendor_owner_ids_for(user)

    if owner_id is not None:
        if ids_qs.filter(pk=owner_id).exists():
            return owner_id
        raise ValueError("Not authorized to act for that vendor owner.")

    count = ids_qs.count()
    if count == 0:
        raise ValueError("You are not a vendor or vendor staff.")
    if count == 1:
        return ids_qs.first()

    raise ValueError("Multiple vendor owners found; specify owner_id.")


def send_activation_email(request, user) -> None:
    """
    Renders and sends the activation email (HTML + text).
    Uses DEFAULT_FROM_EMAIL as sender (explicit).
    """
    try:
        protocol = "https" if request.is_secure() else "http"
        domain = get_current_site(request).domain

        ctx = {
            "user": user,
            "domain": domain,
            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": account_activation_token.make_token(user),
            "protocol": protocol,
        }

        subject = "Activate your account"
        html_body = render_to_string("users/accounts/acc_activate_email.html", ctx)
        text_body = strip_tags(html_body)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,  # ✅ explicit
            to=[user.email],
            headers={"X-Transactional": "account-activation"},
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:
        logger.error("Failed to send activation email to %s: %s", user.email, e, exc_info=True)
        raise

# users/utils.py
from __future__ import annotations
import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q, Exists, OuterRef
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode

from .models import VendorStaff
from .tokens import account_activation_token

logger = logging.getLogger(__name__)
User = get_user_model()


def vendor_owner_ids_for(user):
    """
    Return a queryset of *owner user ids* this user may act for:
      - self, if the user is in the Vendor group
      - any owners where the user has an active VendorStaff membership
    Uses EXISTS so we never return the staff's own id unless they are the owner.
    """
    # self as vendor owner
    self_is_vendor = Q(pk=user.pk, groups__name="Vendor")

    # active membership for this user against the candidate owner (OuterRef("pk"))
    active_staff_for_owner = VendorStaff.objects.filter(
        owner=OuterRef("pk"),  # candidate owner (User row)
        staff=user,
        is_active=True,
    )

    return (
        User.objects
        .filter(self_is_vendor | Exists(active_staff_for_owner))
        .values_list("pk", flat=True)
        .distinct()
    )


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

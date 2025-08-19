from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from ..models import VendorStaff

logger = logging.getLogger(__name__)

TOKEN_SALT = "vendor-staff"
TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
RESEND_COOLDOWN = timedelta(minutes=5)


def invite_vendor_staff(request, owner_id: int, staff, resend: bool = False) -> Dict[str, Any]:
    if owner_id == getattr(staff, "id", None):
        return {"emailed": False, "created": False, "message": "Owner cannot invite themselves."}

    with transaction.atomic():
        vs, created = VendorStaff.objects.select_for_update().get_or_create(
            owner_id=owner_id, staff=staff
        )

        if vs.status == "accepted" or vs.is_active:
            return {
                "id": vs.id,
                "owner_id": vs.owner_id,
                "staff_id": vs.staff_id,
                "status": vs.status,
                "is_active": vs.is_active,
                "created": False,
                "emailed": False,
                "message": "already a member",
            }

        if not created and vs.status != "pending":
            vs.status = "pending"
            vs.save(update_fields=["status"])

        now = timezone.now()
        if (
            not resend
            and vs.status == "pending"
            and vs.last_emailed_at
            and vs.last_emailed_at > now - RESEND_COOLDOWN
        ):
            return {
                "id": vs.id,
                "owner_id": vs.owner_id,
                "staff_id": vs.staff_id,
                "status": vs.status,
                "is_active": vs.is_active,
                "created": created,
                "emailed": False,
                "message": "recently emailed",
            }

        token = signing.dumps({"vs_id": vs.id, "staff_id": staff.id}, salt=TOKEN_SALT)
        accept_url = request.build_absolute_uri(
            reverse("vendor-staff-accept", args=[token])
        )

        def _send():
            subject = "Vendor staff invitation"
            text_body = f"You have been invited to join as vendor staff. Accept the invitation: {accept_url}"
            html_body = f"<p>You have been invited to join as vendor staff.</p><p><a href=\"{accept_url}\">Accept invitation</a></p>"
            email = EmailMultiAlternatives(subject, text_body, to=[staff.email])
            email.attach_alternative(html_body, "text/html")
            try:
                email.send()
                VendorStaff.objects.filter(pk=vs.pk).update(last_emailed_at=timezone.now())
                logger.info(
                    "Sent vendor staff invite",
                    extra={"vendor_staff_id": vs.id, "owner_id": owner_id, "staff_id": staff.id},
                )
            except Exception:
                logger.exception(
                    "Failed to send vendor staff invite",
                    extra={"vendor_staff_id": vs.id, "owner_id": owner_id, "staff_id": staff.id},
                )

        transaction.on_commit(_send)

        result = {
            "id": vs.id,
            "owner_id": vs.owner_id,
            "staff_id": vs.staff_id,
            "status": vs.status,
            "is_active": vs.is_active,
            "created": created,
            "emailed": True,
            "message": "invitation sent",
        }

    return result


def accept_vendor_staff_invite(token: str, user_id: Optional[int]) -> Dict[str, Any]:
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.SignatureExpired:
        return {"code": 400, "message": "token expired"}
    except signing.BadSignature:
        return {"code": 400, "message": "invalid token"}

    vs_id = payload.get("vs_id")
    staff_id = payload.get("staff_id")

    if user_id is not None and user_id != staff_id:
        return {"code": 403, "message": "forbidden"}

    with transaction.atomic():
        try:
            vs = VendorStaff.objects.select_for_update().get(id=vs_id, staff_id=staff_id)
        except VendorStaff.DoesNotExist:
            return {"code": 404, "message": "invite not found"}

        if vs.status == "accepted":
            return {
                "code": 200,
                "message": "already accepted",
                "id": vs.id,
                "owner_id": vs.owner_id,
                "staff_id": vs.staff_id,
                "status": vs.status,
                "is_active": vs.is_active,
                "accepted_at": vs.accepted_at,
            }

        vs.status = "accepted"
        vs.accepted_at = timezone.now()
        vs.save(update_fields=["status", "accepted_at"])

        return {
            "code": 200,
            "message": "accepted",
            "id": vs.id,
            "owner_id": vs.owner_id,
            "staff_id": vs.staff_id,
            "status": vs.status,
            "is_active": vs.is_active,
            "accepted_at": vs.accepted_at,
        }

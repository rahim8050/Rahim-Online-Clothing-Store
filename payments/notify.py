# payments/notify.py
from __future__ import annotations

import logging
from typing import Callable, Optional

from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.db import transaction, IntegrityError

from payments.models import NotificationEvent  # Model lives in payments/models.py

__all__ = ["emit_once", "send_refund_email", "send_payment_email"]

log = logging.getLogger(__name__)


def emit_once(event_key: str, user, channel: str, send_fn: Callable[[], None], payload: Optional[dict] = None) -> bool:
    """
    Insert a NotificationEvent with a unique event_key.
    If it already exists, do nothing (idempotent).
    Execute send_fn AFTER the surrounding DB transaction commits.
    """
    try:
        NotificationEvent.objects.create(
            event_key=event_key,
            user=user if getattr(user, "pk", None) else None,
            channel=channel,
            payload=payload or {},
        )
    except IntegrityError:
        # Already sent for this event key
        return False

    transaction.on_commit(lambda: _safe_send(send_fn))
    return True


def _safe_send(send_fn: Callable[[], None]) -> None:
    try:
        send_fn()
    except Exception as e:  # noqa: BLE001 - we want to log all exceptions from email send
        log.exception("Notification send failed: %s", e)


def _send_html_email(subject: str, to_email: str, text_body: str, html_body: str) -> None:
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
    reply_to = [getattr(settings, "SUPPORT_EMAIL", from_email)]
    msg = EmailMultiAlternatives(subject, text_body, from_email, [to_email], reply_to=reply_to)
    msg.attach_alternative(html_body, "text/html")
    msg.send()


def send_refund_email(
    to_email: str,
    order_no,
    amount,
    reference: str,
    stage: str,  # "completed" or "initiated"
    *,
    refund_id: Optional[str] = None,
    gateway: Optional[str] = None,
    order_url: Optional[str] = None,
    customer_name: Optional[str] = None,
    currency: str = "KES",
) -> None:
    """Send a branded refund email (HTML + text)."""
    site_name = getattr(settings, "SITE_NAME", "Rahim Online")
    support_email = getattr(settings, "SUPPORT_EMAIL", None)
    processed = timezone.now().strftime("%Y-%m-%d %H:%M")

    subject = f"Refund {stage} for Order {order_no}"

    greeting = f"Hi {customer_name}," if customer_name else "Hi,"
    text_body = (
        f"Refund {stage.title()} for Order {order_no}\n\n"
        f"{greeting} your refund has been {stage}.\n\n"
        f"Amount: {currency} {amount}\n"
        f"Payment method: {gateway or ''}\n"
        f"Transaction ref: {reference}\n"
        + (f"Refund id: {refund_id}\n" if refund_id else "")
        + f"Processed at: {processed}\n"
        + (f"\nView your order: {order_url}\n" if order_url else "")
        + (f"\nIf you didn’t request this, contact support at {support_email}."
           if support_email else "\nIf you didn’t request this, contact support.")
    )

    html_body = f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:24px;background:#f6f8fb;font-family:Inter,Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
           style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.05);">
      <tr><td style="padding:24px 24px 8px 24px;">
        <div style="font-size:18px;font-weight:700;color:#111827;">Refund {stage.title()}</div>
        <div style="font-size:14px;color:#6b7280;margin-top:4px;">Order {order_no}</div>
      </td></tr>
      <tr><td style="padding:0 24px 12px 24px;">
        <p style="font-size:14px;color:#111827;margin:0;">{greeting} your refund has been <strong>{stage}</strong>.</p>
      </td></tr>
      <tr><td style="padding:0 24px 16px 24px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
               style="font-size:14px;color:#111827;background:#f9fafb;border-radius:8px;">
          <tr><td style="padding:12px 16px;width:40%;color:#6b7280;">Amount</td>
              <td style="padding:12px 16px;">{currency} {amount}</td></tr>
          <tr><td style="padding:12px 16px;width:40%;color:#6b7280;">Payment method</td>
              <td style="padding:12px 16px;">{gateway or '—'}</td></tr>
          <tr><td style="padding:12px 16px;width:40%;color:#6b7280;">Transaction ref</td>
              <td style="padding:12px 16px;">{reference}</td></tr>
          {f'<tr><td style="padding:12px 16px;width:40%;color:#6b7280;">Refund id</td><td style="padding:12px 16px;">{refund_id}</td></tr>' if refund_id else ''}
          <tr><td style="padding:12px 16px;width:40%;color:#6b7280;">Processed at</td>
              <td style="padding:12px 16px;">{processed}</td></tr>
        </table>
      </td></tr>
      {f'<tr><td style="padding:0 24px 16px 24px;"><a href="{order_url}" style="display:inline-block;background:#111827;color:#ffffff;text-decoration:none;padding:10px 14px;border-radius:8px;font-size:14px;">View your order</a></td></tr>' if order_url else ''}
      <tr><td style="padding:0 24px 24px 24px;">
        <p style="font-size:12px;color:#6b7280;margin:0;">It can take a short time to reflect depending on your bank or wallet.
        {' If you didn’t request this, contact support at ' + support_email if support_email else ' If you didn’t request this, contact support.'}</p>
      </td></tr>
    </table>
    <div style="max-width:640px;margin:12px auto 0;text-align:center;font-size:11px;color:#9ca3af;">{site_name}</div>
  </body>
</html>
"""

    _send_html_email(subject, to_email, text_body, html_body)


def send_payment_email(
    to_email: str,
    order_no,
    amount,
    reference: str,
    stage: str,  # "received", "failed", "cancelled"
    *,
    gateway: Optional[str] = None,
    order_url: Optional[str] = None,
    customer_name: Optional[str] = None,
    currency: str = "KES",
) -> None:
    """Send a branded payment status email (HTML + text)."""
    site_name = getattr(settings, "SITE_NAME", "Rahim Online")
    support_email = getattr(settings, "SUPPORT_EMAIL", None)
    processed = timezone.now().strftime("%Y-%m-%d %H:%M")

    subject = f"Payment {stage} for Order {order_no}"
    greeting = f"Hi {customer_name}," if customer_name else "Hi,"

    text_body = (
        f"Payment {stage.title()} for Order {order_no}\n\n"
        f"{greeting} your payment is {stage}.\n\n"
        f"Amount: {currency} {amount}\n"
        f"Payment method: {gateway or ''}\n"
        f"Transaction ref: {reference}\n"
        f"Processed at: {processed}\n"
        + (f"\nView your order: {order_url}\n" if order_url else "")
        + (f"\nIf you didn’t request this, contact support at {support_email}."
           if support_email else "\nIf you didn’t request this, contact support.")
    )

    html_body = f"""\
<!doctype html>
<html lang="en">
  <body style="margin:0;padding:24px;background:#f6f8fb;font-family:Inter,Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
           style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.05);">
      <tr><td style="padding:24px 24px 8px 24px;">
        <div style="font-size:18px;font-weight:700;color:#111827;">Payment {stage.title()}</div>
        <div style="font-size:14px;color:#6b7280;margin-top:4px;">Order {order_no}</div>
      </td></tr>
      <tr><td style="padding:0 24px 16px 24px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
               style="font-size:14px;color:#111827;background:#f9fafb;border-radius:8px;">
          <tr><td style="padding:12px 16px;width:40%;color:#6b7280;">Amount</td>
              <td style="padding:12px 16px;">{currency} {amount}</td></tr>
          <tr><td style="padding:12px 16px;width:40%;color:#6b7280;">Payment method</td>
              <td style="padding:12px 16px;">{gateway or '—'}</td></tr>
          <tr><td style="padding:12px 16px;width:40%;color:#6b7280;">Transaction ref</td>
              <td style="padding:12px 16px;">{reference}</td></tr>
          <tr><td style="padding:12px 16px;width:40%;color:#6b7280;">Processed at</td>
              <td style="padding:12px 16px;">{processed}</td></tr>
        </table>
      </td></tr>
      {f'<tr><td style="padding:0 24px 16px 24px;"><a href="{order_url}" style="display:inline-block;background:#111827;color:#ffffff;text-decoration:none;padding:10px 14px;border-radius:8px;font-size:14px;">View your order</a></td></tr>' if order_url else ''}
      <tr><td style="padding:0 24px 24px 24px;">
        <p style="font-size:12px;color:#6b7280;margin:0;">If you didn’t request this, contact support{(' at ' + support_email) if support_email else ''}.</p>
      </td></tr>
    </table>
    <div style="max-width:640px;margin:12px auto 0;text-align:center;font-size:11px;color:#9ca3af;">{site_name}</div>
  </body>
</html>
"""
    _send_html_email(subject, to_email, text_body, html_body)

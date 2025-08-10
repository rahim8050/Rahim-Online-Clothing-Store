
import json
import hmac
import hashlib
import time

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.test import Client
from django.urls import reverse, NoReverseMatch

from orders.models import Transaction, Order


class Command(BaseCommand):
    help = "Replay a Paystack webhook locally using Django test client."

    def add_arguments(self, parser):
        parser.add_argument("--reference", help="Transaction reference")
        parser.add_argument("--order", type=int, help="Order ID")
        parser.add_argument(
            "--status",
            default="success",
            choices=["success", "failed", "cancelled", "unknown"],
        )
        parser.add_argument(
            "--verbose-json", action="store_true", help="Print payload and signature"
        )
        parser.add_argument(
            "--send-drone",
            action="store_true",
            help="Run email_recovery_drone after success",
        )

    def handle(self, *args, **options):
        reference = options.get("reference")
        order_id = options.get("order")

        if not reference and not order_id:
            raise CommandError("Provide --reference or --order")

        if not reference:
            try:
                tx = (
                    Transaction.objects.filter(order_id=order_id, gateway="paystack")
                    .latest("created_at")
                )
            except Transaction.DoesNotExist:
                raise CommandError("No Paystack transaction for given order")
            reference = tx.reference
        else:
            try:
                tx = Transaction.objects.get(reference=reference)
            except Transaction.DoesNotExist:
                raise CommandError("Transaction not found")
            order_id = tx.order_id

        status = options["status"]
        event = f"charge.{status}"
        payload = {
            "event": event,
            "data": {"id": int(time.time()), "reference": reference, "status": status},
        }
        body = json.dumps(payload)
        signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode(), body.encode(), hashlib.sha512
        ).hexdigest()

        if options["verbose-json"]:
            self.stdout.write(body)
            self.stdout.write(f"Signature: {signature}")

        try:
            url = reverse("orders:paystack_webhook")
        except NoReverseMatch:
            url = "/orders/paystack/"

        client = Client()
        response = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )
        self.stdout.write(f"Response status: {response.status_code}")

        tx.refresh_from_db()
        order = Order.objects.get(id=order_id)
        self.stdout.write(
            f"Transaction status={tx.status}, callback_received={tx.callback_received}"
        )
        self.stdout.write(
            f"Order paid={order.paid}, payment_status={order.payment_status}"
        )

        # if options["send_drone"] and status == "success":
         
# from django.core.management.base import BaseCommand, CommandError
# from django.conf import settings
# from django.test import Client
# from django.urls import reverse
# from django.utils.timezone import now
# from orders.models import Transaction
# import json, hmac, hashlib

# EVENT_MAP = {
#     "success": "charge.success",
#     "failed": "charge.failed",
#     "cancelled": "charge.cancelled",
#     "unknown": "charge.unknown",
# }

# class Command(BaseCommand):
#     help = "Replay a Paystack webhook locally to update Transaction/Order via the real webhook logic."

#     def add_arguments(self, parser):
#         parser.add_argument("--reference", help="Transaction.reference to replay")
#         parser.add_argument("--order", type=int, help="Order ID to get latest Paystack TX from")
#         parser.add_argument("--status", default="success", choices=list(EVENT_MAP.keys()),
#                             help="Status to simulate (default: success)")
#         parser.add_argument("--verbose-json", action="store_true",
#                             help="Print the signed JSON payload and signature")

#     def handle(self, *args, **opts):
#         reference = opts["reference"]
#         order_id = opts["order"]
#         status = opts["status"]

#         # Determine reference
#         if not reference and not order_id:
#             raise CommandError("Provide either --reference or --order")
#         if order_id and not reference:
#             try:
#                 tx = Transaction.objects.filter(order_id=order_id, gateway="paystack").latest("created_at")
#                 reference = tx.reference
#             except Transaction.DoesNotExist:
#                 raise CommandError(f"No Paystack transaction found for order {order_id}")

#         # Build fake webhook payload
#         event = EVENT_MAP[status]
#         payload = {
#             "event": event,
#             "data": {
#                 "id": int(now().timestamp()),
#                 "reference": reference,
#                 "status": status
#             }
#         }
#         body = json.dumps(payload, separators=(",", ":"))

#         # Sign it
#         secret = getattr(settings, "PAYSTACK_SECRET_KEY", None)
#         if not secret:
#             raise CommandError("PAYSTACK_SECRET_KEY not set in settings.")
#         signature = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha512).hexdigest()

#         if opts["verbose_json"]:
#             self.stdout.write(self.style.NOTICE(f"Payload: {body}"))
#             self.stdout.write(self.style.NOTICE(f"Signature: {signature}"))

#         # Send to real webhook endpoint
#         c = Client()
#         try:
#             url = reverse("orders:paystack_webhook")
#         except Exception:
#             url = "/orders/paystack/"  # fallback

#         headers = {
#             "HTTP_X_PAYSTACK_SIGNATURE": signature,
#             "CONTENT_TYPE": "application/json",
#         }
#         resp = c.post(url, data=body.encode("utf-8"), **headers)

#         self.stdout.write(f"Webhook POST -> {resp.status_code}")
#         if resp.status_code != 200:
#             self.stdout.write(self.style.WARNING(f"Response body: {resp.content.decode()}"))

#         # Show updated transaction info
#         try:
#             tx = Transaction.objects.get(reference=reference, gateway="paystack")
#             self.stdout.write(
#                 f"TX {tx.reference}: status={tx.status}, callback_received={tx.callback_received}, email_sent={tx.email_sent}"
#             )
#             self.stdout.write(
#                 f"Order #{tx.order.id}: paid={tx.order.paid}, payment_status={tx.order.payment_status}"
#             )
#         except Transaction.DoesNotExist:
#             self.stdout.write(self.style.ERROR("Transaction not found after replay."))


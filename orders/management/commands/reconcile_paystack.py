# orders/management/commands/reconcile_paystack.py

import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import EmailDispatchLog, Transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reconcile stale Paystack transactions via the verify API."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=10,
            help="Only reconcile transactions older than this many minutes (default: 10)",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=options["minutes"])
        qs = Transaction.objects.filter(
            gateway="paystack",
            status="unknown",
            callback_received=False,
            created_at__lt=cutoff,
        )

        if not qs.exists():
            self.stdout.write("No stale Paystack transactions to reconcile.")
            return

        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
        for tx in qs:
            url = f"https://api.paystack.co/transaction/verify/{tx.reference}"
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                data = resp.json()
            except Exception as e:
                logger.warning(f"Network error verifying {tx.reference}: {e}")
                continue

            api_ok = data.get("status", False)
            api_status = data.get("data", {}).get("status")

            # Mark the callback as received (we’ve done the manual check)
            tx.callback_received = True
            tx.verified = api_ok and api_status == "success"

            # Map Paystack statuses to our model
            if api_ok and api_status == "success":
                tx.status = "success"
            elif api_ok and api_status in ("failed", "abandoned", "error"):
                tx.status = "failed"
            else:
                # leave it unknown if Paystack didn’t confirm failure
                tx.status = "unknown"

            tx.save(update_fields=["status", "callback_received", "verified"])

            self.stdout.write(self.style.SUCCESS(f"{tx.reference}: reconciled → {tx.status}"))

            # If it succeeded, update order + queue email
            if tx.status == "success" and tx.verified:
                order = tx.order
                order.paid = True
                order.payment_status = "paid"
                order.save(update_fields=["paid", "payment_status"])

                EmailDispatchLog.objects.create(
                    transaction=tx, status="queued", note="Reconciled via verify API"
                )

        self.stdout.write(self.style.SUCCESS("Reconciliation run complete."))

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import requests

from orders.models import Transaction, EmailDispatchLog, Order


class Command(BaseCommand):
    help = "Reconcile missed Paystack webhooks via transaction verify API."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=10)
        txs = Transaction.objects.filter(
            gateway="paystack", status="unknown", created_at__lt=cutoff
        )

        if not txs.exists():
            self.stdout.write("No transactions to reconcile.")
            return

        headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

        for tx in txs:
            url = f"https://api.paystack.co/transaction/verify/{tx.reference}"
            try:
                res = requests.get(url, headers=headers, timeout=30)
                data = res.json()
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"{tx.reference}: error {e}"))
                continue

            status = data.get("data", {}).get("status")
            order = tx.order

            if status == "success":
                tx.status = "success"
                tx.callback_received = True
                tx.save(update_fields=["status", "callback_received"])
                order.paid = True
                order.payment_status = "paid"
                order.save(update_fields=["paid", "payment_status"])
                EmailDispatchLog.objects.create(
                    transaction=tx, status="queued", note="Reconciled via verify"
                )
                self.stdout.write(self.style.SUCCESS(f"{tx.reference}: success"))
            elif status in {"failed", "abandoned"}:
                tx.status = "failed"
                tx.callback_received = True
                tx.save(update_fields=["status", "callback_received"])
                order.payment_status = "failed"
                order.save(update_fields=["payment_status"])
                self.stdout.write(self.style.WARNING(f"{tx.reference}: failed"))
            else:
                self.stdout.write(f"{tx.reference}: pending")

        self.stdout.write(self.style.SUCCESS("Reconciliation complete."))

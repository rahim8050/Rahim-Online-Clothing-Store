from datetime import timedelta

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Transaction


class Command(BaseCommand):
    help = "Verifies stale transactions with Paystack if callback was missed."

    def handle(self, *args, **kwargs):
        cutoff_time = timezone.now() - timedelta(minutes=15)

        stale_transactions = Transaction.objects.filter(
            status="unknown", callback_received=False, created_at__lt=cutoff_time
        )

        for tx in stale_transactions:
            url = f"https://api.paystack.co/transaction/verify/{tx.reference}"
            headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

            try:
                res = requests.get(url, headers=headers, timeout=10)
                data = res.json()

                if data["status"] and data["data"]["status"] == "success":
                    tx.status = "success"
                elif data["status"] and data["data"]["status"] == "failed":
                    tx.status = "failed"
                else:
                    tx.status = "failed"  # Fallback if status is unclear

                tx.callback_received = True  # We confirmed manually
                tx.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[✓] Verified {tx.reference} → {tx.status.upper()}"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"[!] Could not verify {tx.reference}: {str(e)}")
                )

from django.core.management.base import BaseCommand

from orders.models import Order, Transaction
from orders.views import send_payment_receipt_email


class Command(BaseCommand):
    help = (
        "THAAD-3: Resend payment emails for transactions marked success but missing email delivery."
    )

    def handle(self, *args, **kwargs):
        txs = Transaction.objects.filter(status="success", email_sent=False)

        count = 0

        for tx in txs:
            try:
                order = Order.objects.get(id=tx.order_id)
                send_payment_receipt_email(tx, order)
                tx.email_sent = True
                tx.save()
                count += 1
                self.stdout.write(self.style.SUCCESS(f"✅ Email sent for TX: {tx.reference}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠️ Failed for TX: {tx.reference} - {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"🛰️ THAAD-3 completed: {count} email(s) sent."))

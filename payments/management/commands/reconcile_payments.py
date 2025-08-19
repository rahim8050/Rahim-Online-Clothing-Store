from django.core.management.base import BaseCommand

from payments.tasks import reconcile_stale_transactions


class Command(BaseCommand):
    help = "Trigger reconciliation of stale payment transactions"

    def handle(self, *args, **options):
        try:
            reconcile_stale_transactions.delay()
            self.stdout.write(self.style.SUCCESS("Reconciliation task queued"))
        except Exception:
            self.stdout.write("Celery not running, running synchronously")
            reconcile_stale_transactions()
        self.stdout.write(self.style.SUCCESS("Done"))

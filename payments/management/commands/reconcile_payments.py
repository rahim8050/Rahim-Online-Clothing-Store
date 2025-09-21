from django.core.management.base import BaseCommand

from payments.tasks import reconcile_stale_transactions


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--max-age-mins", type=int, default=60)
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--sync", action="store_true")  # bypass Celery

    def handle(self, *args, **opts):
        task_kwargs = dict(
            max_age_mins=opts["max_age_mins"],
            limit=opts["limit"],
            dry_run=opts["dry_run"],
        )
        if opts["sync"]:
            self.stdout.write("Running synchronously")
            reconcile_stale_transactions(**task_kwargs)
        else:
            try:
                reconcile_stale_transactions.delay(**task_kwargs)
                self.stdout.write(self.style.SUCCESS("Reconciliation task queued"))
            except Exception:
                self.stdout.write("Celery not running, running synchronously")
                reconcile_stale_transactions(**task_kwargs)
        self.stdout.write(self.style.SUCCESS("Done"))

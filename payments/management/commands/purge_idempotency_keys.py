from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from payments.models import IdempotencyKey


class Command(BaseCommand):
    help = "Purge idempotency keys older than N days (default 14)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14, help="Age in days to keep (default 14)")

    def handle(self, *args, **options):
        days = int(options.get("days") or 14)
        cutoff = timezone.now() - timedelta(days=days)
        qs = IdempotencyKey.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f"Purged {count} idempotency keys older than {days} days")
        )

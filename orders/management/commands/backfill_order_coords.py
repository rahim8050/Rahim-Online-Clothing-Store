"""Backfill missing order coordinates."""

from django.core.management.base import BaseCommand

from orders.models import Order
from orders.services.destinations import ensure_order_coords


class Command(BaseCommand):
    help = "Geocode recent orders and fill missing coordinates"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument("--only-missing", action="store_true")

    def handle(self, *args, **opts):
        limit = opts["limit"]
        qs = Order.objects.order_by("-id")
        if opts["only_missing"]:
            qs = qs.filter(latitude__isnull=True, longitude__isnull=True)
        qs = qs[:limit]
        updated = skipped = failed = 0
        for order in qs:
            try:
                changed = ensure_order_coords(order)
            except Exception as exc:  # pragma: no cover - defensive
                failed += 1
                self.stderr.write(f"{order.id}: {exc}")
            else:
                if changed:
                    updated += 1
                else:
                    skipped += 1
        self.stdout.write(
            self.style.SUCCESS(f"updated={updated} skipped={skipped} failed={failed}")
        )

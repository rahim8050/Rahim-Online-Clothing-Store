from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from invoicing.models import Invoice
from invoicing.services.etims import submit_invoice


class Command(BaseCommand):
    help = "Submit invoices for an org since N days ago (sandbox)."

    def add_arguments(self, parser):
        parser.add_argument("--org", type=int, required=True, help="VendorOrg ID")
        parser.add_argument("--since", type=int, default=7, help="Days ago to include (default 7)")

    def handle(self, *args, **options):
        org_id = options.get("org")
        days = int(options.get("since") or 7)
        since = timezone.now() - timedelta(days=days)
        qs = Invoice.objects.filter(org_id=org_id, issued_at__gte=since).exclude(status=Invoice.Status.ACCEPTED)
        if not qs.exists():
            self.stdout.write("No invoices to submit")
            return
        for inv in qs.iterator():
            res = submit_invoice(invoice=inv, idempotency_key=f"invoice:submit:{inv.id}")
            self.stdout.write(f"Invoice {inv.id}: {res.status} {res.irn or ''}")


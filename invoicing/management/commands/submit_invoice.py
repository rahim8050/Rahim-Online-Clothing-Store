from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from invoicing.models import Invoice
from invoicing.services.etims import submit_invoice


class Command(BaseCommand):
    help = "Submit a single invoice to eTIMS (sandbox)."

    def add_arguments(self, parser):
        parser.add_argument("--invoice", type=int, required=True, help="Invoice ID")

    def handle(self, *args, **options):
        pk = options.get("invoice")
        try:
            inv = Invoice.objects.get(pk=pk)
        except Invoice.DoesNotExist:
            raise CommandError(f"Invoice {pk} not found")
        if not getattr(settings, "ETIMS_ENABLED", False):
            self.stdout.write(self.style.WARNING("ETIMS disabled; aborting."))
            return
        res = submit_invoice(invoice=inv, idempotency_key=f"invoice:submit:{inv.id}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Submitted invoice {inv.id}: {res.status} {res.irn or ''}"
            )
        )

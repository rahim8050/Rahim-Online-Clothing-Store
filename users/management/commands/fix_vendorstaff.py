from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from users.models import VendorStaff


class Command(BaseCommand):
    help = "Deactivate duplicate active VendorStaff rows, keeping the newest"

    def handle(self, *args, **options):
        deactivated = 0
        pairs = (
            VendorStaff.objects.values("owner_id", "staff_id")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
        )
        with transaction.atomic():
            for pair in pairs:
                memberships = VendorStaff.objects.filter(
                    owner_id=pair["owner_id"], staff_id=pair["staff_id"]
                ).order_by("-created_at", "-id")
                keep = memberships.first()
                for member in memberships[1:]:
                    if member.is_active:
                        member.is_active = False
                        member.save(update_fields=["is_active"])
                        deactivated += 1
        self.stdout.write(f"Pairs processed: {pairs.count()}")
        self.stdout.write(f"Memberships deactivated: {deactivated}")

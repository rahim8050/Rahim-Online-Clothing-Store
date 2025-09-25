from django.core.management.base import BaseCommand
from django.db.models import Count, F, Q

from users.models import VendorStaff


class Command(BaseCommand):
    help = "Audit VendorStaff for common data issues"

    def handle(self, *args, **options):
        qs = VendorStaff.objects.all()

        self_links = qs.filter(owner=F("staff"))
        self.stdout.write(f"Self links: {self_links.count()}")
        for vs in self_links:
            self.stdout.write(f"  - id={vs.id} owner={vs.owner_id}")

        exact_dups = (
            qs.values("owner_id", "staff_id", "role", "is_active")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
        )
        self.stdout.write(f"Exact duplicates: {exact_dups.count()}")
        for row in exact_dups:
            self.stdout.write(
                f"  - owner={row['owner_id']} staff={row['staff_id']} role={row['role']} is_active={row['is_active']} count={row['c']}"
            )

        active_dups = (
            qs.filter(is_active=True)
            .values("owner_id", "staff_id")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
        )
        self.stdout.write(f"Active duplicates: {active_dups.count()}")
        for row in active_dups:
            self.stdout.write(
                f"  - owner={row['owner_id']} staff={row['staff_id']} active_count={row['c']}"
            )

        inactive_blockers = (
            qs.filter(is_active=False)
            .values("owner_id", "staff_id")
            .annotate(
                inactive_count=Count("id"),
                active_count=Count("id", filter=Q(is_active=True)),
            )
            .filter(active_count=0)
        )
        self.stdout.write(
            f"Inactive rows blocking re-invite: {inactive_blockers.count()}"
        )
        for row in inactive_blockers:
            self.stdout.write(
                f"  - owner={row['owner_id']} staff={row['staff_id']} inactive_count={row['inactive_count']}"
            )

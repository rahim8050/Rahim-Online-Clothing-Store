import json
from datetime import timedelta

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from users.models import VendorStaff


class Command(BaseCommand):
    help = "Report health of VendorStaff records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Age in days for pending invites considered stale",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff = timezone.now() - timedelta(days=days)

        duplicates_qs = (
            VendorStaff.objects.values("owner_id", "staff_id")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        inconsistent_qs = VendorStaff.objects.filter(
            (Q(status="accepted") & Q(is_active=False))
            | (~Q(status="accepted") & Q(is_active=True))
        )

        stale_qs = VendorStaff.objects.filter(
            status="pending", invited_at__lt=cutoff
        )

        group_users = []
        group = Group.objects.filter(name="VENDOR_STAFF").first()
        if group:
            group_users = list(
                group.user_set.annotate(
                    active_memberships=Count(
                        "vendor_memberships",
                        filter=Q(vendor_memberships__is_active=True),
                    )
                )
                .filter(active_memberships=0)
                .values_list("id", flat=True)
            )

        report = {
            "duplicates": {
                "count": duplicates_qs.count(),
                "rows": list(duplicates_qs),
            },
            "inconsistent_status": {
                "count": inconsistent_qs.count(),
                "rows": list(
                    inconsistent_qs.values(
                        "id", "owner_id", "staff_id", "status", "is_active"
                    )
                ),
            },
            "stale_pending_invites": {
                "count": stale_qs.count(),
                "rows": list(
                    stale_qs.values("id", "owner_id", "staff_id", "invited_at")
                ),
                "days": days,
            },
            "vendor_staff_group_without_active_memberships": {
                "count": len(group_users),
                "user_ids": group_users,
            },
        }

        self.stdout.write(json.dumps(report, indent=2))

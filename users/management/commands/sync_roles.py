# users/management/commands/sync_roles.py
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from users.constants import ADMIN, ALL_GROUPS, CUSTOMER, DRIVER, VENDOR, VENDOR_STAFF

ROLE_PERMS = {
    ADMIN: ["add_user", "change_user", "delete_user", "view_user"],
    VENDOR: [
        "add_product",
        "change_product",
        "delete_product",
        "view_product",
        "view_order",
    ],
    VENDOR_STAFF: ["add_product", "change_product", "view_product", "view_order"],
    DRIVER: ["view_order", "change_order"],
    CUSTOMER: ["view_product", "add_order"],
}

BAD_GROUP_ALIASES = ["VendorStaff", "vendor staff", "Vendor  Staff"]


def sync_roles(dry_run: bool = False, stdout=None):
    """
    Idempotently create/normalize auth groups and attach permissions.
    Returns a tuple: (processed_count, missing_perm_codenames_sorted)
    """
    missing = set()

    with transaction.atomic():
        for name in ALL_GROUPS:
            group, _ = Group.objects.get_or_create(name=name)
            wanted = set(ROLE_PERMS.get(name, []))

            perms = list(Permission.objects.filter(codename__in=wanted))
            found = {p.codename for p in perms}
            missing |= wanted - found

            if not dry_run:
                group.permissions.set(perms)  # idempotent

            if stdout:
                stdout.write(f"Ensured group {name} with {len(perms)} perms")

        # migrate bad aliases to canonical VENDOR_STAFF
        for bad in BAD_GROUP_ALIASES:
            try:
                legacy = Group.objects.get(name=bad)
            except Group.DoesNotExist:
                continue

            good, _ = Group.objects.get_or_create(name=VENDOR_STAFF)
            for u in legacy.user_set.all():
                if not dry_run:
                    u.groups.add(good)
            if not dry_run:
                legacy.delete()

            if stdout:
                stdout.write(f"Migrated group '{bad}' → '{VENDOR_STAFF}'")

    return len(ALL_GROUPS), sorted(missing)


class Command(BaseCommand):
    help = "Create/normalize auth groups and permissions (safe to run repeatedly)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Show actions without writing"
        )

    def handle(self, *args, **options):
        processed, missing = sync_roles(dry_run=options["dry_run"], stdout=self.stdout)
        tag = "DRY-RUN " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"{tag}Processed {processed} groups"))
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f"Missing permission codenames: {', '.join(missing)}"
                )
            )

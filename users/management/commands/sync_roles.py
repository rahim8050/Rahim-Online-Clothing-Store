from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from users.constants import ALL_GROUPS, VENDOR, VENDOR_STAFF, DRIVER, ADMIN, CUSTOMER

ROLE_PERMS = {
    ADMIN: ["add_user", "change_user", "delete_user", "view_user"],
    VENDOR: ["add_product", "change_product", "delete_product", "view_product", "view_order"],
    VENDOR_STAFF: ["add_product", "change_product", "view_product", "view_order"],
    DRIVER: ["view_order", "change_order"],
    CUSTOMER: ["view_product", "add_order"],
}


class Command(BaseCommand):
    help = "Create/normalize auth groups and permissions"

    def handle(self, *args, **kwargs):
        for name in ALL_GROUPS:
            g, _ = Group.objects.get_or_create(name=name)
            codenames = set(ROLE_PERMS.get(name, []))
            perms = Permission.objects.filter(codename__in=codenames)
            g.permissions.set(perms)
            self.stdout.write(self.style.SUCCESS(f"Ensured group {name} with {len(perms)} perms"))

        for bad in ["VendorStaff", "vendor staff", "Vendor  Staff"]:
            try:
                b = Group.objects.get(name=bad)
                good, _ = Group.objects.get_or_create(name=VENDOR_STAFF)
                for u in b.user_set.all():
                    u.groups.add(good)
                b.delete()
                self.stdout.write(self.style.WARNING(f"Migrated group '{bad}' → '{VENDOR_STAFF}'"))
            except Group.DoesNotExist:
                pass

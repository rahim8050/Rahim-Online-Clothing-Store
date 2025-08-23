from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

class Command(BaseCommand):
    help = "Create demo Vendor and Driver users and assign them to the right groups."

    def add_arguments(self, parser):
        parser.add_argument("--vendors", type=int, default=1)
        parser.add_argument("--drivers", type=int, default=1)
        parser.add_argument("--password", type=str, default="Password123!")
        parser.add_argument("--prefix", type=str, default="demo")

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        pwd = opts["password"]
        prefix = opts["prefix"]

        vendor_group, _ = Group.objects.get_or_create(name="Vendor")
        driver_group, _ = Group.objects.get_or_create(name="Driver")

        created = []

        for i in range(1, opts["vendors"] + 1):
            username = f"{prefix}_vendor{i}"
            user, new = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com", "is_active": True},
            )
            if new:
                user.set_password(pwd)
                user.save()
            user.groups.add(vendor_group)
            created.append((username, "Vendor"))

        for i in range(1, opts["drivers"] + 1):
            username = f"{prefix}_driver{i}"
            user, new = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.com", "is_active": True},
            )
            if new:
                user.set_password(pwd)
                user.save()
            user.groups.add(driver_group)
            created.append((username, "Driver"))

        self.stdout.write(self.style.SUCCESS("✅ Seed complete"))
        for uname, role in created:
            self.stdout.write(f"  - {uname} / {pwd}  [{role}]")

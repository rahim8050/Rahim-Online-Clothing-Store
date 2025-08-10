from django.core.management.base import BaseCommand

from users.roles import sync_roles


class Command(BaseCommand):
    help = "Synchronize role groups and permissions"

    def handle(self, *args, **options):
        sync_roles()
        self.stdout.write(self.style.SUCCESS("Roles synced"))


from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete staff users who are inactive and older than 3 days"

    def handle(self, *args, **kwargs):
        User = get_user_model()
        cutoff_date = timezone.now() - timedelta(days=3)

        users_to_delete = User.objects.filter(
            is_staff=True, is_active=False, date_joined__lt=cutoff_date
        )

        count = users_to_delete.count()
        users_to_delete.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} inactive staff users created more than 3 days ago."
            )
        )

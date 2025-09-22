from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Set django.contrib.sites domain and name from settings/env"

    def handle(self, *args, **options):
        site_id = getattr(settings, "SITE_ID", 1)
        domain = getattr(settings, "SITE_DOMAIN", "127.0.0.1:8000")
        name = getattr(settings, "SITE_NAME", "Rahim Online Dev")
        site, _created = Site.objects.update_or_create(
            id=site_id, defaults={"domain": domain, "name": name}
        )
        self.stdout.write(self.style.SUCCESS(f"Site {site.id} => {site.domain} ({site.name})"))

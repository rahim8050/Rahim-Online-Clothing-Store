from django.core.management.base import BaseCommand

from orders.assignment import pick_warehouse
from orders.models import OrderItem


class Command(BaseCommand):
    help = "Audit tracking data and optionally fix missing warehouses"

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="assign missing warehouses")
        parser.add_argument("--default-lat", type=float, help="latitude for orders missing coords")
        parser.add_argument("--default-lng", type=float, help="longitude for orders missing coords")

    def handle(self, *args, **opts):
        fix = opts.get("fix")
        default_lat = opts.get("default_lat")
        default_lng = opts.get("default_lng")

        qs = OrderItem.objects.select_related("order").filter(warehouse__isnull=True)
        total = qs.count()
        assigned = 0

        for item in qs:
            lat = item.order.latitude
            lng = item.order.longitude
            if (lat is None or lng is None) and default_lat is not None and default_lng is not None:
                lat = default_lat
                lng = default_lng
                if fix:
                    item.order.latitude = lat
                    item.order.longitude = lng
                    item.order.save(update_fields=["latitude", "longitude"])
            if lat is None or lng is None:
                continue
            wh = pick_warehouse(lat, lng)
            if wh and fix:
                item.warehouse = wh
                item.save(update_fields=["warehouse"])
                assigned += 1

        self.stdout.write(f"items missing warehouse: {total}")
        if fix:
            self.stdout.write(f"assigned: {assigned}")

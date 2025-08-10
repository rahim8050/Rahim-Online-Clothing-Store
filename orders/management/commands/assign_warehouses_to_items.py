"""Assign nearest warehouses to order items lacking one."""

from django.core.management.base import BaseCommand

from orders.models import OrderItem
from product_app.models import Warehouse


class Command(BaseCommand):
    help = "Assign the nearest warehouse to order items without one"

    def handle(self, *args, **options):
        warehouses = list(Warehouse.objects.all())
        if not warehouses:
            self.stdout.write(self.style.WARNING("No warehouses available."))
            return

        assigned = 0
        qs = OrderItem.objects.select_related("order").filter(warehouse__isnull=True)
        for item in qs:
            if item.order.latitude is None or item.order.longitude is None:
                continue
            order_lat = item.order.latitude
            order_lng = item.order.longitude
            nearest = min(
                warehouses,
                key=lambda w: (w.latitude - order_lat) ** 2 + (w.longitude - order_lng) ** 2,
            )
            item.warehouse = nearest
            item.save(update_fields=["warehouse"])
            assigned += 1

        self.stdout.write(
            self.style.SUCCESS(f"Assigned warehouses to {assigned} order items.")
        )


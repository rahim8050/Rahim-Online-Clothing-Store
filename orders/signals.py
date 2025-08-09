from django.db.models.signals import post_save
from django.dispatch import receiver

from .assignment import pick_warehouse
from .models import OrderItem


@receiver(post_save, sender=OrderItem)
def assign_warehouse_on_create(sender, instance, created, **kwargs):
    if not created or instance.warehouse_id:
        return
    order = instance.order
    wh = pick_warehouse(order.latitude, order.longitude)
    if wh:
        instance.warehouse = wh
        instance.save(update_fields=["warehouse"])

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .assignment import pick_warehouse
from .services.destinations import ensure_order_coords
from .models import Order, OrderItem

logger = logging.getLogger(__name__)



@receiver(post_save, sender=OrderItem)
def assign_warehouse_on_create(sender, instance, created, **kwargs):
    if not created or instance.warehouse_id:
        return
    order = instance.order
    wh = pick_warehouse(order.latitude, order.longitude)
    if wh:
        instance.warehouse = wh
        instance.save(update_fields=["warehouse"])


@receiver(post_save, sender=Order)
def geocode_order_on_save(sender, instance, created, **kwargs):
    if instance.latitude is not None and instance.longitude is not None:
        return
    if not instance.address:
        return
    try:
        ensure_order_coords(instance)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Order geocode signal failed: %s", exc)

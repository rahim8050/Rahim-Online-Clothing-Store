import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .assignment import pick_warehouse
from .models import Delivery, Order, OrderItem
from .services.destinations import ensure_order_coords

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


@receiver(post_save, sender=Delivery)
def broadcast_delivery_update(sender, instance: Delivery, **kwargs):  # pragma: no cover - IO
    """Broadcast delivery status updates to its WS group with stable payload."""
    try:
        layer = get_channel_layer()
        if not layer:
            return
        payload = {
            "type": "status.update",
            "id": instance.pk,
            "status": instance.status,
            "assigned_at": instance.assigned_at and instance.assigned_at.isoformat(),
            "picked_up_at": instance.picked_up_at and instance.picked_up_at.isoformat(),
            "delivered_at": instance.delivered_at and instance.delivered_at.isoformat(),
        }
        async_to_sync(layer.group_send)(instance.ws_group, payload)
    except Exception as exc:
        logger.warning("Delivery broadcast failed: %s", exc)

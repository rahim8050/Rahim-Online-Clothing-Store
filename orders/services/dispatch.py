"""Utility helpers for dispatching order items."""

from django.core.exceptions import ValidationError


def mark_item_dispatched(item):
    """Mark an ``OrderItem`` as dispatched with basic safety checks.

    Raises:
        ValidationError: if the item lacks a warehouse or the parent order has
            no destination coordinates.
    """

    if item.warehouse_id is None:
        raise ValidationError("Cannot dispatch without assigned warehouse.")

    order = item.order
    if order.latitude is None or order.longitude is None:
        raise ValidationError("Cannot dispatch without order coordinates.")

    item.delivery_status = "dispatched"
    item.save(update_fields=["delivery_status"])
    return item


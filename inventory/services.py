from __future__ import annotations

import os
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from product_app.models import ProductStock
from django.db.models import Sum


def _publish_vendor(owner_id: int, event: str, payload: dict | None = None) -> None:
    """
    Send a websocket event to a vendor's group.
    """
    layer = get_channel_layer()
    if not layer:
        return

    data: dict[str, object] = {
        "type": "vendor.event",
        "t": event,
        "rid": payload.get("rid") if payload else None,
    }

    if payload:
        data.update(payload)

    async_to_sync(layer.group_send)(f"vendor.{owner_id}", data)


def check_low_stock_and_notify(product) -> None:
    """
    Checks if a product's total stock is below a threshold and notifies the vendor.
    """
    try:
        threshold = int(os.getenv("LOW_STOCK_THRESHOLD", "3"))
    except Exception:
        threshold = 3

    total = (
        ProductStock.objects.filter(product=product)
        .aggregate(total=Sum("quantity"))
        .get("total", 0)
        or 0
    )

    if total <= threshold:
        owner_id = getattr(product, "owner_id", None)
        if owner_id:
            _publish_vendor(owner_id, "inventory.low_stock", {"rid": product.id})

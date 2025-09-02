from __future__ import annotations

import os
from decimal import Decimal
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from product_app.models import ProductStock


def _publish_vendor(owner_id: int, event: str, payload: dict | None = None):
    layer = get_channel_layer()
    if not layer:
        return
    data = {"type": "vendor.event", "t": event, "rid": payload.get("rid") if payload else None}
    if payload:
        data.update(payload)
    async_to_sync(layer.group_send)(f"vendor.{owner_id}", data)


def check_low_stock_and_notify(product) -> None:
    try:
        threshold = int(os.getenv("LOW_STOCK_THRESHOLD", "3"))
    except Exception:
        threshold = 3
    try:
        total = ProductStock.objects.filter(product=product).aggregate_total = sum(
            s.quantity for s in ProductStock.objects.filter(product=product)
        )
    except Exception:
        total = 0
    if total <= threshold:
        owner_id = getattr(product, "owner_id", None)
        if owner_id:
            _publish_vendor(owner_id, "inventory.low_stock", {"rid": product.id})


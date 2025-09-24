from django.core.exceptions import ValidationError
from django.db import models

from product_app.models import ProductStock

from .models import AuditLog


def safe_decrement_stock(order, request_id: str = ""):
    for item in order.items.select_for_update():
        if not item.warehouse:
            continue
        ps = ProductStock.objects.select_for_update().get(
            product=item.product, warehouse=item.warehouse
        )
        if ps.quantity < item.quantity:
            raise ValidationError("Insufficient stock")
        ps.quantity = models.F("quantity") - item.quantity
        ps.save(update_fields=["quantity"])
        AuditLog.log(
            event="STOCK_DECREMENT",
            order=order,
            request_id=request_id,
            meta={"product": item.product_id, "quantity": item.quantity},
        )


def set_order_paid(order, request_id: str = ""):
    updates: list[str] = []
    if getattr(order, "payment_status", "").lower() != "paid":
        order.payment_status = "paid"
        updates.append("payment_status")
    if not getattr(order, "paid", False):
        order.paid = True
        updates.append("paid")
    if hasattr(order, "stock_updated") and not getattr(order, "stock_updated", False):
        order.stock_updated = True
        updates.append("stock_updated")
    if updates:
        order.save(update_fields=updates)
    AuditLog.log(event="ORDER_PAID", order=order, request_id=request_id)

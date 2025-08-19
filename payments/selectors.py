from django.db import transaction as dbtx, models
from django.core.exceptions import ValidationError

from .models import AuditLog
from product_app.models import ProductStock


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
    order.payment_status = "PAID"
    order.save(update_fields=["payment_status"])
    AuditLog.log(event="ORDER_PAID", order=order, request_id=request_id)

"""Order-related services."""

from typing import Iterable, Tuple

from django.db import transaction
from django.db.models import F

from product_app.models import Product, ProductStock

from users.permissions import NotBuyingOwnListing

from ..assignment import pick_warehouse
from ..models import Order, OrderItem


def create_order_from_cart(user, cart):
    perm = NotBuyingOwnListing()
    with transaction.atomic():
        order = Order.objects.create(
            user=user,
            full_name="F",
            email="e@e.com",
            address="A",
            dest_address_text="A",
            dest_lat=0,
            dest_lng=0,
        )
        product_ids = [i.product_id for i in cart.items.select_related("product")]
        products = {
            p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
        }

        for item in cart.items.all():
            product = products.get(item.product_id)
            if product is None:
                continue
            if perm._is_forbidden(user, product):
                raise PermissionError("Attempted self-purchase in order creation")
            OrderItem.objects.create(
                order=order,
                product=product,
                price=product.price,
                quantity=item.quantity,
            )

        if not order.items.exists():
            raise ValueError("No valid items to order")
        return order


def create_order_with_items(user, cart: Iterable[Tuple], coords=None):
    """Create an Order and OrderItems, ensuring warehouse assignment."""
    lat, lng = coords if coords else (None, None)
    order = Order.objects.create(
        user=user,
        full_name="F",
        email="e@e.com",
        address="A",
        latitude=lat,
        longitude=lng,
        dest_address_text="A",
        dest_lat=lat or 0,
        dest_lng=lng or 0,
    )
    for product, qty in cart:
        wh = pick_warehouse(lat, lng)
        OrderItem.objects.create(
            order=order,
            product=product,
            price=product.price,
            quantity=qty,
            warehouse=wh,
            delivery_status="dispatched",
        )
    return order


def assign_warehouses_and_update_stock(order):
    """Assign nearest warehouse to each item and atomically decrement stock."""
    if order.latitude is None or order.longitude is None or order.stock_updated:
        return
    with transaction.atomic():
        items = order.items.select_for_update().select_related("product")
        for item in items:
            if not item.warehouse_id:
                stock_entry = get_nearest_stock(
                    item.product, order.latitude, order.longitude
                )
                if not stock_entry:
                    raise ValueError("No stock available")
                item.warehouse = stock_entry.warehouse
                item.save(update_fields=["warehouse"])
            updated = ProductStock.objects.filter(
                product=item.product,
                warehouse=item.warehouse,
                quantity__gte=item.quantity,
            ).update(quantity=F("quantity") - item.quantity)
            if updated == 0:
                raise ValueError("Insufficient stock")
        order.stock_updated = True
        order.save(update_fields=["stock_updated"])


def get_nearest_stock(product, latitude, longitude):
    """Return nearest ProductStock with available quantity."""
    customer_location = (latitude, longitude)
    stocks = ProductStock.objects.filter(product=product, quantity__gt=0).select_related("warehouse")
    nearest = None
    min_distance = None
    for stock in stocks:
        warehouse_loc = (stock.warehouse.latitude, stock.warehouse.longitude)
        # Simple distance approximation (km)
        d_lat = (warehouse_loc[0] - latitude) ** 2
        d_lng = (warehouse_loc[1] - longitude) ** 2
        distance = (d_lat + d_lng) ** 0.5
        if min_distance is None or distance < min_distance:
            min_distance = distance
            nearest = stock
    return nearest

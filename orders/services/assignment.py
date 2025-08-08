from geopy.distance import geodesic
from product_app.models import ProductStock

def get_nearest_stock(product, latitude, longitude):
    """Return nearest ProductStock with available quantity."""
    customer_location = (latitude, longitude)
    stocks = ProductStock.objects.filter(product=product, quantity__gt=0).select_related("warehouse")
    nearest = None
    min_distance = None
    for stock in stocks:
        warehouse_loc = (stock.warehouse.latitude, stock.warehouse.longitude)
        distance = geodesic(customer_location, warehouse_loc).kilometers
        if min_distance is None or distance < min_distance:
            min_distance = distance
            nearest = stock
    return nearest

def assign_warehouses_and_update_stock(order):
    """Assign nearest warehouse to each item and decrement stock once."""
    if order.latitude is None or order.longitude is None or order.stock_updated:
        return
    for item in order.items.select_related("product"):
        if item.warehouse_id:
            continue
        stock_entry = get_nearest_stock(item.product, order.latitude, order.longitude)
        if stock_entry:
            item.warehouse = stock_entry.warehouse
            item.save(update_fields=["warehouse"])
            stock_entry.quantity = max(0, stock_entry.quantity - item.quantity)
            stock_entry.save(update_fields=["quantity"])
    order.stock_updated = True
    order.save(update_fields=["stock_updated"])

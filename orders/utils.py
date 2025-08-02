import requests
from requests.structures import CaseInsensitiveDict
from django.conf import settings

api_key = settings.GEOAPIFY_API_KEY


def reverse_geocode(lat, lon):
    url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={api_key}"

    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()  # Parsed JSON response
    else:
        return {
            "error": f"Failed to reverse geocode: {response.status_code}",
            "status_code": response.status_code,
        }

def get_nearest_stock(product, latitude, longitude):
    """Return the ProductStock entry for the nearest warehouse with available stock."""
    from product_app.models import ProductStock
    from geopy.distance import geodesic

    customer_location = (latitude, longitude)
    stocks = ProductStock.objects.filter(product=product, quantity__gt=0).select_related(
        "warehouse"
    )

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
    """Assign the nearest warehouse to each order item and deduct stock."""
    if order.stock_updated:
        return
    for item in order.items.select_related("product"):
        if order.latitude is None or order.longitude is None:
            continue
        stock_entry = get_nearest_stock(item.product, order.latitude, order.longitude)
        if stock_entry:
            item.warehouse = stock_entry.warehouse
            item.save()
            stock_entry.quantity = max(0, stock_entry.quantity - item.quantity)
            stock_entry.save()
    order.stock_updated = True
    order.save()

# yourapp/utils/geoapify.py
import requests
from django.conf import settings


def reverse_geocode(lat, lon):
    api_key = settings.GEOAPIFY_API_KEY
    print(api_key)
    url = f"https://api.geoapify.com/v1/geocode/reverse?" f"lat={lat}&lon={lon}&apiKey={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None


import logging

from django.core.exceptions import FieldDoesNotExist

logger = logging.getLogger(__name__)

VENDOR_FIELDS = ["vendor", "owner", "user", "created_by"]


def get_vendor_field(model):
    for field in VENDOR_FIELDS:
        try:
            model._meta.get_field(field)
            return field
        except FieldDoesNotExist:
            continue
    logger.warning("No vendor FK field found on %s; defaulting to 'vendor'", model.__name__)
    return "vendor"

# yourapp/utils/geoapify.py
import requests
from django.conf import settings

def reverse_geocode(lat, lon):
    api_key = settings.GEOAPIFY_API_KEY
    print(api_key)
    url = (
        f"https://api.geoapify.com/v1/geocode/reverse?"
        f"lat={lat}&lon={lon}&apiKey={api_key}"
    )
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

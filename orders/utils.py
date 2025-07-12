# myapp/utils/geoapify.py
import requests
from requests.structures import CaseInsensitiveDict
from django.conf import settings
api_key = settings.GEOAPIFY_API_KEY

def reverse_geocode(lat, lon):
    
    print("Using loaded key:", api_key)    # Debugging line to check if the key is loaded correctly
    url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={api_key}"

    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json"

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()  # Parsed JSON response
    else:
        return {
            "error": f"Failed to reverse geocode: {response.status_code}",
            "status_code": response.status_code
        }

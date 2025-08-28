import requests
from requests.structures import CaseInsensitiveDict
from django.conf import settings

from decimal import Decimal, ROUND_HALF_UP
Q2 = Decimal("0.01")

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






def D(x):  # safe Decimal
    return x if isinstance(x, Decimal) else Decimal(str(x))

def q2(x):  # 2dp HALF_UP
    return D(x).quantize(Q2, rounding=ROUND_HALF_UP)

def to_minor_units(amount) -> int:
    return int((q2(amount) * 100).to_integral_value(rounding=ROUND_HALF_UP))

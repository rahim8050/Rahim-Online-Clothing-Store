from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from orders.models import Order
from orders.services.destinations import ensure_order_coords
from orders.services.geocoding import geocode_address


class GeocodeAddressTests(SimpleTestCase):
    @override_settings(GEOAPIFY_API_KEY="x")
    @patch("orders.services.geocoding.httpx.Client.get")
    def test_fallback_to_nominatim(self, mock_get):
        geo_resp = Mock(status_code=500, json=Mock(return_value={}))
        nom_resp = Mock(status_code=200, json=Mock(return_value=[{"lat": "1", "lon": "2"}]))
        mock_get.side_effect = [geo_resp, nom_resp]
        coords = geocode_address("addr")
        self.assertEqual(coords, (1.0, 2.0))
        self.assertEqual(mock_get.call_count, 2)


class EnsureOrderCoordsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        from django.utils.crypto import get_random_string
        self.user = User.objects.create_user(username="u", password=get_random_string(12))  # nosec B106

    @patch("orders.services.destinations.geocode_address")
    def test_updates_missing_coords(self, mock_geo):
        mock_geo.return_value = (1.1, 2.2)
        order = Order.objects.create(
            user=self.user,
            full_name="F",
            email="e@e.com",
            address="A",
            dest_address_text="A",
            dest_lat=0,
            dest_lng=0,
        )
        order.latitude = None
        order.longitude = None
        order.save(update_fields=["latitude", "longitude"])
        changed = ensure_order_coords(order)
        self.assertTrue(changed)
        order.refresh_from_db()
        self.assertAlmostEqual(order.latitude, 1.1)
        self.assertAlmostEqual(order.longitude, 2.2)

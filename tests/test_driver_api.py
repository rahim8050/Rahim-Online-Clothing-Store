import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rahim_Online_ClothesStore.settings")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DEBUG", "1")
import django

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase, override_settings

from orders.geo import haversine_km
from orders.models import Delivery, Order

django.setup()

User = get_user_model()

@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    GEOAPIFY_API_KEY=None,
)
class DriverAPITests(TestCase):
    def setUp(self):
        self.client = Client()

    def _skip_if_no_migrations(self):
        if "users_customuser" not in connection.introspection.table_names():
            self.skipTest("migrations not applied")

    def test_deliveries_api_latlng(self):
        self._skip_if_no_migrations()
        driver = User.objects.create_user(username="drv", password="x")
        cust = User.objects.create_user(username="cust", password="x")
        order = Order.objects.create(
            user=cust,
            full_name="A",
            email="a@a.com",
            latitude=-1.292066,
            longitude=36.821945,
            dest_lat=-1.292066,
            dest_lng=36.821945,
        )
        Delivery.objects.create(
            order=order,
            driver=driver,
            last_lat=-1.30,
            last_lng=36.82,
            status=Delivery.Status.ASSIGNED,
        )
        self.client.force_login(driver)
        r = self.client.get("/orders/apis/driver/deliveries/")
        data = r.json()[0]
        self.assertEqual(data["dest_lat"], -1.292066)
        self.assertEqual(data["dest_lng"], 36.821945)
        self.assertEqual(data["last_lat"], -1.3)
        self.assertEqual(data["last_lng"], 36.82)
        self.assertIsInstance(data["dest_lat"], float)

    def test_route_api_flips_geojson(self):
        self._skip_if_no_migrations()
        driver = User.objects.create_user(username="drv2", password="x")
        cust = User.objects.create_user(username="cust2", password="x")
        order = Order.objects.create(
            user=cust,
            full_name="A",
            email="a@a.com",
            latitude=-1.292,
            longitude=36.822,
            dest_lat=-1.292,
            dest_lng=36.822,
        )
        d = Delivery.objects.create(
            order=order,
            driver=driver,
            last_lat=-1.30,
            last_lng=36.82,
            dest_lat=-1.292,
            dest_lng=36.822,
            status=Delivery.Status.ASSIGNED,
        )
        self.client.force_login(driver)
        with patch("orders.views._osrm_route") as mock_route:
            mock_route.return_value = {
                "coords": [[36.82, -1.29], [36.83, -1.28]],
                "distance_km": 1.0,
                "duration_min": 2.0,
            }
            r = self.client.get(f"/orders/apis/driver/route/{d.id}/")
        data = r.json()
        self.assertEqual(data["coords"], [[-1.29, 36.82], [-1.28, 36.83]])

    def test_no_atlantic_line(self):
        self._skip_if_no_migrations()
        driver = User.objects.create_user(username="drv3", password="x")
        cust = User.objects.create_user(username="cust3", password="x")
        order = Order.objects.create(
            user=cust,
            full_name="A",
            email="a@a.com",
            latitude=-1.292066,
            longitude=36.821945,
            dest_lat=-1.292066,
            dest_lng=36.821945,
        )
        d = Delivery.objects.create(
            order=order,
            driver=driver,
            last_lat=-1.30,
            last_lng=36.82,
            dest_lat=-1.292066,
            dest_lng=36.821945,
            status=Delivery.Status.ASSIGNED,
        )
        self.client.force_login(driver)
        with patch("orders.views._osrm_route") as mock_route:
            mock_route.return_value = {
                "coords": [[-1.30, 36.82], [-1.292066, 36.821945]],
                "distance_km": 2.0,
                "duration_min": 3.0,
            }
            r = self.client.get(f"/orders/apis/driver/route/{d.id}/")
        data = r.json()
        first, last = data["coords"][0], data["coords"][-1]
        dist_line = haversine_km(first[0], first[1], last[0], last[1])
        dist_last_dest = haversine_km(
            float(d.last_lat), float(d.last_lng), float(d.dest_lat), float(d.dest_lng)
        )
        self.assertLess(dist_line, 20)
        self.assertLess(dist_last_dest, 20)
        self.assertLess(dist_line, 1000)

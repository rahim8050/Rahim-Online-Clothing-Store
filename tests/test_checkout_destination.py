from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from cart.models import Cart, CartItem
from orders.models import Order
from product_app.models import Category, Product


class CheckoutDestinationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p")
        self.client.login(username="u", password="p")
        cat = Category.objects.create(name="c", slug="c")
        prod = Product.objects.create(category=cat, name="p", slug="p", price=10)
        cart = Cart.objects.create()
        CartItem.objects.create(cart=cart, product=prod, quantity=1, is_selected=True)
        sess = self.client.session
        sess["cart_id"] = cart.id
        sess.save()

    def test_post_without_coords(self):
        resp = self.client.post(
            reverse("orders:order_create"),
            {
                "full_name": "F",
                "email": "e@e.com",
                "address": "A",
                "payment_method": "card",
                "dest_address_text": "A",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    def test_post_with_valid_coords(self):
        resp = self.client.post(
            reverse("orders:order_create"),
            {
                "full_name": "F",
                "email": "e@e.com",
                "address": "Umoja",
                "payment_method": "card",
                "dest_address_text": "Umoja",
                "dest_lat": "1.0",
                "dest_lng": "36.8",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.dest_address_text, "Umoja")
        self.assertEqual(order.dest_lat, Decimal("1.0"))
        self.assertEqual(order.dest_lng, Decimal("36.8"))


class GeoAutocompleteViewTests(TestCase):
    @override_settings(GEOAPIFY_API_KEY="key")
    @patch("orders.views.requests.get")
    def test_proxy_ok(self, mock_get):
        mock_get.return_value.ok = True
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "results": [{"formatted": "Umoja", "lat": 1, "lon": 2}]
        }
        resp = self.client.get(
            reverse("orders:geo-autocomplete"), {"q": "Umo"}, REMOTE_ADDR="1.1.1.1"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.json())
        mock_get.assert_called_once()

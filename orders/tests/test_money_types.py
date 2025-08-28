# orders/tests/test_money_types.py
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from product_app.models import Category, Product
from cart.models import Cart, CartItem
from orders.models import Order

class MoneyTypesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="rahim",
            password="x",
            email="r@x.x",
        )
        self.client = Client()
        self.client.login(username="rahim", password="x")

        # minimal catalog
        cat = Category.objects.create(name="Shirts", slug="shirts")
        self.product = Product.objects.create(
            category=cat,
            name="Tee",
            slug="tee",
            price=Decimal("123.45"),
        )

        # cart in session
        self.cart = Cart.objects.create()
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2,
            is_selected=True,
        )

    def test_checkout_decimal_safety(self):
        # attach cart to session
        s = self.client.session
        s["cart_id"] = self.cart.id
        s.save()

        # GET to render form (optional)
        self.client.get(reverse("orders:order_create"))

        # POST payload — include address + dest_* to satisfy the form/view
        resp = self.client.post(
            reverse("orders:order_create"),
            data={
                "full_name": "Rahim",
                "email": "r@x.x",
                "address": "Nairobi",                 # some forms still require it
                "payment_method": "card",
                "dest_address_text": "Nairobi CBD",
                "dest_lat": "1.000000",
                "dest_lng": "36.800000",
            },
            follow=True,
        )

        self.assertIn(resp.status_code, (200, 302))
        self.assertTrue(Order.objects.exists())

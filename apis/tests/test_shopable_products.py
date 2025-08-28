import django
django.setup()
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from users.models import CustomUser, VendorStaff
from product_app.models import Product, Category


class ShopableProductsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_vendor_does_not_see_own_products(self):
        owner = CustomUser.objects.create_user(username="owner", email="owner@example.com", password="x")
        other = CustomUser.objects.create_user(username="other", email="other@example.com", password="x")
        cat = Category.objects.create(name="Shirts", slug="shirts")
        Product.objects.create(name="My Shirt", slug="my-shirt", price=1000, available=True, owner=owner, category=cat)
        Product.objects.create(name="Other Shirt", slug="other-shirt", price=1200, available=True, owner=other, category=cat)

        self.client.login(username="owner", email="owner@example.com", password="x")
        url = reverse("shopable-products")
        data = self.client.get(url).json()
        results = data.get("results") or data
        names = [r["name"] for r in results]
        self.assertNotIn("My Shirt", names)
        self.assertIn("Other Shirt", names)

    def test_staff_excluded_from_boss_products(self):
        boss = CustomUser.objects.create_user(username="boss", email="boss@example.com", password="x")
        staff = CustomUser.objects.create_user(username="staff", email="staff@example.com", password="x")
        VendorStaff.objects.create(owner=boss, staff=staff, is_active=True)
        cat = Category.objects.create(name="Pants", slug="pants")
        Product.objects.create(name="Boss Item", slug="boss-item", price=500, available=True, owner=boss, category=cat)

        self.client.login(username="staff", email="staff@example.com", password="x")
        url = reverse("shopable-products")
        data = self.client.get(url).json()
        results = data.get("results") or data
        names = [r["name"] for r in results]
        self.assertNotIn("Boss Item", names)

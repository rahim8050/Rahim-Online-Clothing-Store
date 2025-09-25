from django.contrib.auth import get_user_model
from django.test import TestCase

from orders.models import Order, OrderItem
from orders.services import assign_warehouses_and_update_stock
from product_app.models import Category, Product, ProductStock, Warehouse


class StockDeductionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p")
        self.cat = Category.objects.create(name="c", slug="c")
        self.product = Product.objects.create(
            category=self.cat, name="p", slug="p", price=10
        )
        self.wh = Warehouse.objects.create(name="w", latitude=1.0, longitude=36.0)
        ProductStock.objects.create(product=self.product, warehouse=self.wh, quantity=5)

    def _make_order(self, qty):
        order = Order.objects.create(
            user=self.user,
            full_name="F",
            email="e@e.com",
            address="A",
            latitude=1.0,
            longitude=36.0,
            dest_address_text="A",
            dest_lat=1.0,
            dest_lng=36.0,
        )
        OrderItem.objects.create(
            order=order, product=self.product, price=10, quantity=qty, warehouse=self.wh
        )
        return order

    def test_deducts_stock_atomically(self):
        order = self._make_order(3)
        assign_warehouses_and_update_stock(order)
        stock = ProductStock.objects.get(product=self.product, warehouse=self.wh)
        self.assertEqual(stock.quantity, 2)

    def test_raises_on_insufficient_stock(self):
        order = self._make_order(10)
        with self.assertRaises(ValueError):
            assign_warehouses_and_update_stock(order)

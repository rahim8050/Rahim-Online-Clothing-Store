# payments/tests/test_stock_decrement.py
from django.db import transaction
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import F

from orders.models import Order, OrderItem
from product_app.models import Product, ProductStock, Warehouse
from payments.services import process_success
from payments.selectors import safe_decrement_stock

def make_product_with_stock(qty=8):
    p = Product.objects.create(name="Test Tee", sku="TEE-001", price=100)
    w = Warehouse.objects.create(name="Main WH")
    s = ProductStock.objects.create(product=p, warehouse=w, quantity=qty)
    return p, s, w

def make_order(product, qty=1):
    o = Order.objects.create(
        full_name="Rahim", email="r@example.com", address="Nairobi",
        # optional coords fields omitted
    )
    OrderItem.objects.create(order=o, product=product, quantity=qty, unit_price=product.price)
    return o

class TestStockDecrement(TestCase):
    def test_single_purchase_from_eight_leaves_seven(self):
        """n=8, buy 1 → 7 (n-1)"""
        product, stock, _ = make_product_with_stock(8)
        order = make_order(product, qty=1)

        # Either call process_success(...) (uses safe_decrement_stock) or call selector directly.
        process_success(order_id=order.id, request_id="req-1", paid_at=timezone.now())

        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 7)

    def test_eight_single_purchases_runs_to_zero_and_blocks_ninth(self):
        """Eight successive purchases of qty=1 exhaust stock: 8→7→...→0; 9th should fail."""
        product, stock, _ = make_product_with_stock(8)

        for i in range(8):
            order = make_order(product, qty=1)
            process_success(order_id=order.id, request_id=f"req-{i}", paid_at=timezone.now())

        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 0)

        # 9th purchase must raise and not go negative
        order9 = make_order(product, qty=1)
        with self.assertRaises(ValidationError):
            process_success(order_id=order9.id, request_id="req-9", paid_at=timezone.now())

        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 0)

    def test_bulk_purchase_of_8_from_8_leaves_zero(self):
        """n=8, buy 8 → 0."""
        product, stock, _ = make_product_with_stock(8)
        order = make_order(product, qty=8)
        process_success(order_id=order.id, request_id="req-bulk", paid_at=timezone.now())

        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 0)

    def test_insufficient_stock_raises_and_no_decrement(self):
        """n=1, buy 2 → ValidationError; stays 1."""
        product, stock, _ = make_product_with_stock(1)
        order = make_order(product, qty=2)
        with self.assertRaises(ValidationError):
            process_success(order_id=order.id, request_id="req-over", paid_at=timezone.now())
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 1)

    def test_concurrent_last_unit_one_succeeds_one_fails(self):
        """
        Simulate two checkouts racing for the last unit.
        This assumes safe_decrement_stock uses select_for_update + F() atomics.
        """
        product, stock, _ = make_product_with_stock(1)
        o1 = make_order(product, qty=1)
        o2 = make_order(product, qty=1)

        # T1: lock & decrement succeeds
        with transaction.atomic():
            safe_decrement_stock(order=o1, request_id="c1")
            # commit T1 (release locks)
        # T2: now tries; must fail due to 0 left
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                safe_decrement_stock(order=o2, request_id="c2")

        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 0)

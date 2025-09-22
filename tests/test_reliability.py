from decimal import Decimal
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from orders.models import Order, OrderItem
from payments.selectors import safe_decrement_stock
from payments.services import process_payout
from product_app.models import Category, Product, ProductStock, Warehouse

pytestmark = pytest.mark.django_db


def make_catalog(qty=5):
    cat = Category.objects.create(name="Tees", slug="tees")
    p = Product.objects.create(
        category=cat, name="Test Tee", slug="test-tee", price=Decimal("100.00")
    )
    wh = Warehouse.objects.create(name="Main WH", latitude=0.02, longitude=36.8, address="Nairobi")
    stock = ProductStock.objects.create(product=p, warehouse=wh, quantity=qty)
    return p, stock, wh


def make_order(product, wh, qty=1):
    User = get_user_model()
    suffix = uuid4().hex[:6]
    u = User.objects.create_user(
        username=f"u{qty}-{suffix}", email=f"u{qty}-{suffix}@ex.com", password="x"
    )
    o = Order.objects.create(
        full_name="Rahim",
        email="r@example.com",
        address="Nairobi",
        dest_address_text="Somewhere",
        dest_lat=0.1,
        dest_lng=36.9,
        user=u,
    )
    OrderItem.objects.create(
        order=o, product=product, quantity=qty, price=product.price, warehouse=wh
    )
    return o


def test_idempotent_payout_retry():
    r1 = process_payout(org_id=1, amount=Decimal("500.00"), idempotency_key="k-1")
    r2 = process_payout(org_id=1, amount=Decimal("500.00"), idempotency_key="k-1")
    assert r1 == r2


def test_concurrent_stock_decrement_n_minus_1():
    product, stock, wh = make_catalog(qty=1)
    o1 = make_order(product, wh, qty=1)
    o2 = make_order(product, wh, qty=1)

    with transaction.atomic():
        safe_decrement_stock(order=o1, request_id="r1")
    with pytest.raises(ValidationError):
        with transaction.atomic():
            safe_decrement_stock(order=o2, request_id="r2")
    stock.refresh_from_db()
    assert stock.quantity == 0


def test_no_negative_stock_with_constraints():
    product, stock, wh = make_catalog(qty=1)
    o = make_order(product, wh, qty=2)
    with pytest.raises(ValidationError):
        with transaction.atomic():
            safe_decrement_stock(order=o, request_id="over")
    stock.refresh_from_db()
    assert stock.quantity == 1

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from orders.models import Order, OrderItem, Transaction
from product_app.models import Category, Product


@pytest.mark.django_db
def test_vendor_kpis_scoped(client):
    User = get_user_model()
    g_vendor, _ = Group.objects.get_or_create(name="Vendor")

    owner = User.objects.create_user(username="owner1", email="o1@example.com", password="x")
    owner.groups.add(g_vendor)
    other = User.objects.create_user(username="owner2", email="o2@example.com", password="x")
    other.groups.add(g_vendor)

    # Category
    c = Category.objects.create(name="c", slug="c")

    # Products for each owner
    p1 = Product.objects.create(
        category=c, owner=owner, name="A", slug="a", price=10, available=True
    )
    p2 = Product.objects.create(
        category=c, owner=other, name="B", slug="b", price=20, available=True
    )

    # One order for owner, one for other
    o1 = Order.objects.create(
        full_name="x",
        email="e@example.com",
        address="a",
        dest_address_text="d",
        dest_lat=0,
        dest_lng=0,
        user=owner,
    )
    OrderItem.objects.create(order=o1, product=p1, price=10, quantity=1)
    Transaction.objects.create(
        user=owner,
        order=o1,
        amount=10,
        method="card",
        gateway="paystack",
        status="success",
        reference="r1",
    )

    o2 = Order.objects.create(
        full_name="x2",
        email="e2@example.com",
        address="a2",
        dest_address_text="d2",
        dest_lat=0,
        dest_lng=0,
        user=other,
    )
    OrderItem.objects.create(order=o2, product=p2, price=20, quantity=1)
    Transaction.objects.create(
        user=other,
        order=o2,
        amount=20,
        method="card",
        gateway="paystack",
        status="success",
        reference="r2",
    )

    client.force_login(owner)
    # As owner1, KPI must only include owner1 data
    resp = client.get("/apis/vendor/kpis/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["products"]["total"] >= 1
    assert data["orders_30d"] >= 1
    assert data["revenue_30d"] >= 10
    assert len(data["series_14d"]) == 14

    # Cross vendor access by owner2 should be separate (log in as other)
    client.logout()
    client.force_login(other)
    resp2 = client.get("/apis/vendor/kpis/")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["revenue_30d"] >= 20
    # ensure the two vendors do not see the same revenue sum
    assert data2["revenue_30d"] != data["revenue_30d"]


@pytest.mark.django_db
def test_vendor_endpoints_permission(client):
    """Non-vendors must be denied on vendor-only endpoints."""
    User = get_user_model()
    u = User.objects.create_user(username="cust", email="c@example.com", password="x")
    client.force_login(u)
    r = client.get("/apis/vendor/kpis/")
    assert r.status_code in (401, 403)

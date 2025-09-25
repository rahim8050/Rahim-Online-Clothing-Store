from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from orders.models import Order
from payments.models import Transaction
from vendor_app.kpi import (
    aggregate_kpis_daily,
    bump_realtime_on_success,
    get_realtime_kpi_snapshot,
)
from vendor_app.models import VendorMember, VendorOrg, VendorProfile

pytestmark = pytest.mark.django_db


def mk_user(username: str):
    User = get_user_model()
    return User.objects.create_user(
        username=username, email=f"{username}@ex.com", password="x"
    )


def seed_org():
    owner = mk_user("owner3")
    org = VendorOrg.objects.create(name="Org3", slug="org3", owner=owner)
    VendorMember.objects.create(org=org, user=owner, role=VendorMember.Role.OWNER)
    VendorProfile.objects.create(user=owner, org=org)
    return owner, org


def mk_order_for(user):
    return Order.objects.create(
        user=user,
        full_name="B",
        email=user.email,
        address="A",
        dest_address_text="D",
        dest_lat=0.1,
        dest_lng=36.8,
    )


def test_kpi_daily_aggregation_consistency():
    owner, org = seed_org()
    buyer = mk_user("buyer3")
    order = mk_order_for(buyer)
    # record a transaction tied to org
    from django.utils import timezone

    txn = Transaction.objects.create(
        order=order,
        user=buyer,
        method="card",
        gateway="paystack",
        amount=Decimal("100.00"),
        currency="KES",
        status="success",
        idempotency_key="i1",
        reference="r1",
        vendor_org=org,
        gross_amount=Decimal("100.00"),
        net_to_vendor=Decimal("98.00"),
        processed_at=timezone.now(),
    )
    from decimal import Decimal as D

    assert txn.vendor_org == org

    kpi = aggregate_kpis_daily(org.id)
    assert kpi.orders >= 1 and kpi.gross_revenue >= D("100.00")


def test_realtime_snapshot_monotonicity():
    owner, org = seed_org()
    snap1 = get_realtime_kpi_snapshot(org.id)
    bump_realtime_on_success(org.id, Decimal("10.00"), Decimal("9.00"))
    snap2 = get_realtime_kpi_snapshot(org.id)
    assert Decimal(str(snap2["gross_revenue"])) >= Decimal(
        str(snap1.get("gross_revenue", "0.00"))
    )


def test_permissions_kpi_visibility():
    owner, org = seed_org()
    client = APIClient()
    client.force_authenticate(user=owner)
    resp = client.get(f"/apis/v1/vendor/orgs/{org.id}/kpis/?window=daily&last_n=1")
    assert resp.status_code == 200
    resp = client.get(f"/apis/v1/vendor/orgs/{org.id}/kpis/realtime/")
    assert resp.status_code == 200

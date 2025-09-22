import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from orders.models import Order, OrderItem
from payments.models import PaymentEvent, Payout, Transaction
from product_app.models import Category, Product, ProductStock, Warehouse
from vendor_app.models import VendorMember, VendorOrg, VendorProfile

pytestmark = pytest.mark.django_db


def setup_org_environment(rate=Decimal("0.02")):
    User = get_user_model()
    owner = User.objects.create_user(username="owner", email="o@example.com", password="x")
    org = VendorOrg.objects.create(name="Org", slug="org", owner=owner, org_commission_rate=rate)
    VendorMember.objects.create(org=org, user=owner, role=VendorMember.Role.OWNER)
    VendorProfile.objects.create(user=owner, org=org)

    cat = Category.objects.create(name="c", slug="c")
    product = Product.objects.create(
        category=cat, name="tee", slug="tee", price=Decimal("100.00"), owner=owner
    )
    wh = Warehouse.objects.create(name="w", latitude=0.1, longitude=36.8, address="NBO")
    ProductStock.objects.create(product=product, warehouse=wh, quantity=3)

    buyer = User.objects.create_user(username="buyer", email="b@example.com", password="x")
    order = Order.objects.create(
        user=buyer,
        full_name="B",
        email="b@example.com",
        address="A",
        dest_address_text="D",
        dest_lat=Decimal("0.1"),
        dest_lng=Decimal("36.8"),
    )
    OrderItem.objects.create(
        order=order, product=product, quantity=1, price=product.price, warehouse=wh
    )

    txn = Transaction.objects.create(
        order=order,
        user=buyer,
        method="card",
        gateway="paystack",
        amount=Decimal("100.00"),
        currency="KES",
        status="pending",
        idempotency_key="idem-1",
        reference="ref-1",
    )
    return org, order, txn


def test_mpesa_webhook_idempotent_and_org_scoped(client):
    org, order, txn = setup_org_environment()
    # MPESA webhook body (minimal)
    body = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": txn.reference,
                "ResultCode": 0,
                "CallbackMetadata": {"Item": [{"Name": "MpesaReceiptNumber", "Value": "XYZ"}]},
            }
        }
    }
    # First call processes
    resp = client.post(
        reverse("webhook-mpesa"), data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    # Second identical call should be idempotently acknowledged
    resp = client.post(
        reverse("webhook-mpesa"), data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200

    txn.refresh_from_db()
    assert str(txn.gross_amount) == "100.00"
    # rate=2% => 2.00 commission, fees default 0
    assert str(txn.net_to_vendor) == "98.00"
    assert txn.vendor_org_id == org.id

    # PaymentEvent created once and scoped to org
    assert PaymentEvent.objects.filter(reference=txn.reference, vendor_org=org).count() == 1

    # Payout created for org
    p = Payout.objects.get(transaction=txn)
    assert p.vendor_org_id == org.id and str(p.amount) == "98.00"


def test_paystack_event_fee_breakdown_saved(client, settings):
    settings.PAYSTACK_SECRET_KEY = "secret"
    org, order, txn = setup_org_environment()
    payload = {
        "event": "charge.success",
        "data": {
            "reference": txn.reference,
            "status": "success",
            "amount": 10000,
        },
    }
    raw = json.dumps(payload).encode()
    sig = hmac.new(b"secret", raw, hashlib.sha512).hexdigest()
    resp = client.post(
        reverse("webhook-paystack"),
        raw,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=sig,
    )
    assert resp.status_code == 200
    txn.refresh_from_db()
    assert str(txn.gross_amount) == "100.00"
    assert str(txn.net_to_vendor) == "98.00"
    assert PaymentEvent.objects.filter(
        reference=txn.reference, vendor_org=org, provider="paystack"
    ).exists()


def test_org_payout_calculation(client):
    org, order, txn = setup_org_environment(rate=Decimal("0.05"))  # 5%
    body = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": txn.reference,
                "ResultCode": 0,
                "CallbackMetadata": {"Item": []},
            }
        }
    }
    resp = client.post(
        reverse("webhook-mpesa"), data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    txn.refresh_from_db()
    # 5% commission on 100 => net 95
    assert str(txn.net_to_vendor) == "95.00"

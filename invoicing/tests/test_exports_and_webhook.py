import pytest
import hmac
import hashlib
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from vendor_app.models import VendorOrg, VendorMember, VendorProfile
from orders.models import Order
from invoicing.models import Invoice, InvoiceLine


pytestmark = pytest.mark.django_db


def mk_user(username: str):
    User = get_user_model()
    return User.objects.create_user(username=username, email=f"{username}@ex.com", password="x")


def seed_invoice():
    owner = mk_user("ownerx")
    org = VendorOrg.objects.create(name="OrgX", slug="orgx", owner=owner)
    VendorMember.objects.create(org=org, user=owner, role=VendorMember.Role.OWNER)
    VendorProfile.objects.create(user=owner, org=org)
    # create a minimal order
    order = Order.objects.create(user=owner, full_name="B", email=owner.email, address="A", dest_address_text="D", dest_lat=0.1, dest_lng=36.8)
    inv = Invoice.objects.create(org=org, order=order, buyer_name="BuyerX")
    InvoiceLine.objects.create(invoice=inv, name="L1", qty=Decimal("1"), unit_price=Decimal("10.00"), tax_rate=Decimal("0.16"))
    return owner, org, inv


def test_invoice_list_filters_and_permissions():
    owner, org, inv = seed_invoice()
    client = APIClient()
    client.force_authenticate(user=owner)
    resp = client.get("/apis/v1/invoicing/invoices/?org=%d&status=draft" % org.id)
    assert resp.status_code == 200
    data = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
    assert any((row.get("id") == inv.id) for row in data)


def test_pdf_generation_and_signed_url(settings):
    owner, org, inv = seed_invoice()
    client = APIClient()
    client.force_authenticate(user=owner)
    resp = client.get(f"/apis/v1/invoicing/invoices/{inv.id}/download/")
    assert resp.status_code == 200
    assert resp.data.get("pdf_url")


def test_etims_webhook_updates_state_idempotently(settings, client):
    settings.ETIMS_WEBHOOK_SECRET = "sek"
    owner, org, inv = seed_invoice()
    import json
    payload = {"invoice_id": inv.id, "status": "accepted", "irn": "IRN-TEST"}
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(b"sek", raw, hashlib.sha256).hexdigest()
    url = "/apis/v1/invoicing/etims/webhook"
    r1 = client.post(url, data=raw, content_type="application/json", HTTP_X_ETIMS_SIGNATURE=sig)
    assert r1.status_code == 200
    inv.refresh_from_db()
    assert inv.status == "accepted" and inv.irn
    # Replay is idempotent and returns 200
    r2 = client.post(url, data=raw, content_type="application/json", HTTP_X_ETIMS_SIGNATURE=sig)
    assert r2.status_code == 200

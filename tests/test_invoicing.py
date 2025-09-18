import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model

from vendor_app.models import VendorOrg, VendorMember, VendorProfile
from invoicing.models import Invoice, InvoiceLine
from orders.models import Order


pytestmark = pytest.mark.django_db


def mk_user(username: str):
    User = get_user_model()
    return User.objects.create_user(username=username, email=f"{username}@ex.com", password="x")


def mk_order():
    u = mk_user("buyer")
    return Order.objects.create(
        user=u,
        full_name="Buyer",
        email=u.email,
        address="Nairobi",
        dest_address_text="Somewhere",
        dest_lat=Decimal("0.10"),
        dest_lng=Decimal("36.80"),
    )


def mk_org():
    owner = mk_user("owner")
    org = VendorOrg.objects.create(name="Org", slug="org", owner=owner)
    VendorMember.objects.create(org=org, user=owner, role=VendorMember.Role.OWNER)
    VendorProfile.objects.create(user=owner, org=org)
    return org


def test_invoice_totals_consistency():
    org = mk_org()
    order = mk_order()
    inv = Invoice.objects.create(org=org, order=order, buyer_name="Buyer")
    InvoiceLine.objects.create(invoice=inv, sku="SKU1", name="Item 1", qty=Decimal("2"), unit_price=Decimal("10.00"), tax_rate=Decimal("0.16"))
    InvoiceLine.objects.create(invoice=inv, sku="SKU2", name="Item 2", qty=Decimal("1"), unit_price=Decimal("5.00"), tax_rate=Decimal("0.16"))
    inv.save()  # recompute totals
    inv.refresh_from_db()
    assert str(inv.subtotal) == "25.00"
    assert str(inv.tax_amount) == "4.00"
    assert str(inv.total) == "29.00"


def test_unique_invoice_per_order():
    import django.db
    org = mk_org()
    order = mk_order()
    Invoice.objects.create(org=org, order=order, buyer_name="B")
    with pytest.raises(django.db.utils.IntegrityError):
        Invoice.objects.create(org=org, order=order, buyer_name="B2")


def test_line_calculation_quantization():
    org = mk_org()
    order = mk_order()
    inv = Invoice.objects.create(org=org, order=order, buyer_name="Buyer")
    line = InvoiceLine.objects.create(invoice=inv, sku="SKU3", name="Item 3", qty=Decimal("1"), unit_price=Decimal("99.995"), tax_rate=Decimal("0.1600"))
    assert str(line.line_total) == "100.00"
    assert str(line.tax_total) == "16.00"

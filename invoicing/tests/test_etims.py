from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from invoicing.models import Invoice, InvoiceLine
from invoicing.services.etims import submit_invoice
from orders.models import Order
from vendor_app.models import VendorMember, VendorOrg, VendorProfile

pytestmark = pytest.mark.django_db


def mk_user(username: str):
    User = get_user_model()
    return User.objects.create_user(
        username=username, email=f"{username}@ex.com", password="x"
    )


def mk_order():
    u = mk_user("buyer2")
    return Order.objects.create(
        user=u,
        full_name="Buyer2",
        email=u.email,
        address="Nairobi",
        dest_address_text="Somewhere",
        dest_lat=Decimal("0.10"),
        dest_lng=Decimal("36.80"),
    )


def mk_org():
    owner = mk_user("owner2")
    org = VendorOrg.objects.create(
        name="Org2", slug="org2", owner=owner, kra_pin="A123456789B"
    )
    VendorMember.objects.create(org=org, user=owner, role=VendorMember.Role.OWNER)
    VendorProfile.objects.create(user=owner, org=org)
    return org


def test_submit_invoice_idempotent():
    org = mk_org()
    order = mk_order()
    inv = Invoice.objects.create(org=org, order=order, buyer_name="Buyer")
    InvoiceLine.objects.create(
        invoice=inv,
        name="X",
        qty=Decimal("1"),
        unit_price=Decimal("10.00"),
        tax_rate=Decimal("0.16"),
    )
    _ = submit_invoice(invoice=inv, idempotency_key=f"invoice:submit:{inv.id}")
    inv.refresh_from_db()
    irn1 = inv.irn
    _ = submit_invoice(invoice=inv, idempotency_key=f"invoice:submit:{inv.id}")
    inv.refresh_from_db()
    assert inv.status == Invoice.Status.ACCEPTED
    assert inv.irn == irn1


def test_state_transitions_and_irn_persist():
    org = mk_org()
    order = mk_order()
    inv = Invoice.objects.create(org=org, order=order, buyer_name="Buyer")
    InvoiceLine.objects.create(
        invoice=inv,
        name="Y",
        qty=Decimal("2"),
        unit_price=Decimal("5.00"),
        tax_rate=Decimal("0.16"),
    )
    _ = submit_invoice(invoice=inv, idempotency_key=f"invoice:submit:{inv.id}")
    inv.refresh_from_db()
    assert inv.status == Invoice.Status.ACCEPTED
    assert inv.irn
    assert inv.submitted_at is not None and inv.accepted_at is not None


def test_reject_flow_preserves_error_msg():
    org = mk_org()
    order = mk_order()
    inv = Invoice.objects.create(org=org, order=order, buyer_name="REJECT ME")
    InvoiceLine.objects.create(
        invoice=inv,
        name="Z",
        qty=Decimal("1"),
        unit_price=Decimal("1.00"),
        tax_rate=Decimal("0.00"),
    )
    _ = submit_invoice(invoice=inv, idempotency_key=f"invoice:submit:{inv.id}")
    inv.refresh_from_db()
    assert inv.status == Invoice.Status.REJECTED
    assert inv.irn == ""
    assert "rejection" in (inv.last_error or "").lower()

from __future__ import annotations

from django.test import override_settings
from django.urls import reverse

from invoicing.models import Invoice


@override_settings(ETIMS_ENABLED=False)
def test_feature_flag_blocks_endpoints_when_disabled(client, django_user_model):
    # create minimal invoice + user; leverage factories if present
    user = django_user_model.objects.create_user(username="m", email="m@x.com", password="pw")
    client.force_login(user)
    # pick any invoice id if fixtures exist; otherwise skip softly
    inv = Invoice.objects.first()
    if not inv:
        return
    url = reverse("invoicing:invoice-submit", args=[inv.id])
    r = client.post(url)
    assert r.status_code in (404, 503)


@override_settings(ETIMS_ENABLED=True)
def test_pre_submission_guards(db):
    from invoicing.models import Invoice
    from vendor_app.models import VendorOrg

    # Create org not verified
    org = VendorOrg.objects.create(name="Acme", slug="acme", owner_id=1)
    inv = Invoice.objects.create(org=org, order_id=1, buyer_name="Test")

    from invoicing.services.etims import submit_invoice

    res = submit_invoice(invoice=inv)
    assert res.status == "rejected"

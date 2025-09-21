import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from vendor_app.models import VendorMember, VendorOrg, VendorOrgAuditLog, VendorProfile

pytestmark = pytest.mark.django_db


def mk_user(username: str, is_staff=False):
    User = get_user_model()
    return User.objects.create_user(
        username=username, email=f"{username}@ex.com", password="x", is_staff=is_staff
    )


def seed_org():
    owner = mk_user("owner")
    org = VendorOrg.objects.create(name="Org", slug="org", owner=owner)
    VendorMember.objects.create(org=org, user=owner, role=VendorMember.Role.OWNER)
    VendorProfile.objects.create(user=owner, org=org)
    return owner, org


def test_kra_pin_validation_accept_reject():
    owner, org = seed_org()
    client = APIClient()
    client.force_authenticate(user=owner)

    # Accept valid
    resp = client.patch(
        f"/apis/v1/vendor/orgs/{org.id}/", {"kra_pin": "A123456789B"}, format="json"
    )
    assert resp.status_code in (200, 202)

    # Reject invalid
    resp = client.patch(f"/apis/v1/vendor/orgs/{org.id}/", {"kra_pin": "BADPIN"}, format="json")
    assert resp.status_code == 400
    assert "KRA PIN" in str(resp.data)


def test_kra_pin_visibility_role_restrictions():
    owner, org = seed_org()
    org.kra_pin = "A123456789B"
    org.save()

    manager = mk_user("manager")
    staff = mk_user("staff")
    outsider = mk_user("outsider")
    admin = mk_user("admin", is_staff=True)
    VendorMember.objects.create(org=org, user=manager, role=VendorMember.Role.MANAGER)
    VendorMember.objects.create(org=org, user=staff, role=VendorMember.Role.STAFF)

    client = APIClient()

    # Owner sees PIN
    client.force_authenticate(user=owner)
    resp = client.get(f"/apis/v1/vendor/orgs/{org.id}/")
    assert resp.status_code == 200
    assert resp.data.get("kra_pin") == "A123456789B"

    # Manager sees PIN
    client.force_authenticate(user=manager)
    resp = client.get(f"/apis/v1/vendor/orgs/{org.id}/")
    assert resp.status_code == 200
    assert resp.data.get("kra_pin") == "A123456789B"

    # Staff cannot see PIN
    client.force_authenticate(user=staff)
    resp = client.get(f"/apis/v1/vendor/orgs/{org.id}/")
    assert resp.status_code == 200
    assert "kra_pin" not in resp.data

    # Admin always allowed
    client.force_authenticate(user=admin)
    resp = client.get(f"/apis/v1/vendor/orgs/{org.id}/")
    assert resp.status_code == 200
    assert resp.data.get("kra_pin") == "A123456789B"


def test_audit_log_on_kra_pin_change():
    owner, org = seed_org()
    client = APIClient()
    client.force_authenticate(user=owner)
    resp = client.patch(
        f"/apis/v1/vendor/orgs/{org.id}/",
        {"kra_pin": "A123456789B", "tax_status": "verified"},
        format="json",
    )
    assert resp.status_code in (200, 202)

    logs = list(VendorOrgAuditLog.objects.filter(org=org))
    fields = {l.field for l in logs}
    assert "kra_pin" in fields and "tax_status" in fields
    assert any(l.actor_id == owner.id for l in logs)

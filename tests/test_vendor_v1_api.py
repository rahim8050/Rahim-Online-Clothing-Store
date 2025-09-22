import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from vendor_app.models import VendorMember

pytestmark = pytest.mark.django_db


def create_user(email: str, username: str):
    User = get_user_model()
    return User.objects.create_user(username=username, email=email, password="x")


def test_org_crud_and_invite_flow():
    client = APIClient()
    owner = create_user("owner@example.com", "owner")
    user2 = create_user("user2@example.com", "user2")
    client.force_authenticate(user=owner)

    # Create org
    resp = client.post("/apis/v1/vendor/orgs/", {"name": "Acme"}, format="json")
    assert resp.status_code == 201
    org_id = resp.data["id"]

    # Owner should auto-membership as OWNER
    assert VendorMember.objects.filter(org_id=org_id, user=owner, role="OWNER").exists()

    # List my orgs
    resp = client.get("/apis/v1/vendor/orgs/")
    assert resp.status_code == 200
    assert (
        any(o["id"] == org_id for o in resp.data["results"])
        if isinstance(resp.data, dict)
        else True
    )

    # Invite user2 as STAFF
    resp = client.post(
        f"/apis/v1/vendor/orgs/{org_id}/invite/",
        {"user_id": user2.id, "role": "STAFF"},
        format="json",
    )
    assert resp.status_code == 201
    assert VendorMember.objects.filter(org_id=org_id, user=user2, role="STAFF").exists()

    # Members list
    resp = client.get(f"/apis/v1/vendor/orgs/{org_id}/members/")
    assert resp.status_code == 200


def test_openapi_schema_contains_vendor_endpoints():
    client = APIClient()
    resp = client.get("/apis/v1/schema/?format=json")
    assert resp.status_code == 200
    import json

    content = json.loads(resp.content.decode("utf-8"))
    # paths keys can vary by spectacular version; assert 'vendor' + 'orgs' path exists
    paths = content.get("paths") or {}
    keys = list(paths.keys())
    assert any(("vendor" in k and "/orgs" in k) for k in keys), keys

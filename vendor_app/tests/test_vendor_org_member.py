import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from vendor_app.models import VendorOrg, VendorMember, VendorProfile


pytestmark = pytest.mark.django_db


def create_user(email: str, username: str) -> object:
    User = get_user_model()
    return User.objects.create_user(username=username, email=email, password="x")


def test_owner_unique():
    owner = create_user("owner@example.com", "owner")
    u2 = create_user("u2@example.com", "u2")
    org = VendorOrg.objects.create(name="Acme", slug="acme", owner=owner)

    # First owner membership allowed
    VendorMember.objects.create(org=org, user=owner, role=VendorMember.Role.OWNER)

    # Second owner for same org should violate partial unique constraint
    with pytest.raises(IntegrityError):
        VendorMember.objects.create(org=org, user=u2, role=VendorMember.Role.OWNER)


def test_member_roles_and_queries():
    owner = create_user("owner2@example.com", "owner2")
    staff = create_user("staff@example.com", "staff")
    mgr = create_user("mgr@example.com", "mgr")
    org = VendorOrg.objects.create(name="Beta", slug="beta", owner=owner)

    # use helpers
    org.add_member(owner, "OWNER")
    org.add_member(staff, "STAFF")
    org.add_member(mgr, "MANAGER")

    assert org.is_member(owner) is True
    assert org.is_member(staff) is True
    assert org.is_member(mgr) is True

    assert org.has_role(owner, "OWNER") is True
    assert org.has_role(staff, "STAFF") is True
    assert org.has_role(mgr, "MANAGER") is True

    # invalid role
    assert org.has_role(staff, "notarole") is False


def test_org_soft_activation_flags():
    owner = create_user("owner3@example.com", "owner3")
    staff = create_user("staff3@example.com", "staff3")
    org = VendorOrg.objects.create(name="Gamma", slug="gamma", owner=owner)

    m = org.add_member(staff, "STAFF")
    assert m.is_active is True

    # soft deactivate
    m.is_active = False
    m.save(update_fields=["is_active"])
    assert org.is_member(staff) is False

    # re-add reactivates membership
    org.add_member(staff, "STAFF")
    m.refresh_from_db()
    assert m.is_active is True


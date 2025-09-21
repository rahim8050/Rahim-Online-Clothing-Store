import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from vendor_app.models import VendorMember, VendorOrg
from vendor_app.permissions import IsInOrg, IsOrgManager, IsOrgOwner, IsOrgStaff
from vendor_app.selectors import org_scoped_queryset

pytestmark = pytest.mark.django_db


def create_user(email: str, username: str):
    User = get_user_model()
    return User.objects.create_user(username=username, email=email, password="x")


class DummyView:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_permissions_owner_manager_staff_access():
    owner = create_user("own@example.com", "own")
    manager = create_user("mgr@example.com", "mgr")
    staff = create_user("stf@example.com", "stf")
    outsider = create_user("out@example.com", "out")

    org = VendorOrg.objects.create(name="Org", slug="org", owner=owner)

    VendorMember.objects.create(org=org, user=owner, role=VendorMember.Role.OWNER)
    VendorMember.objects.create(org=org, user=manager, role=VendorMember.Role.MANAGER)
    VendorMember.objects.create(org=org, user=staff, role=VendorMember.Role.STAFF)

    rf = APIRequestFactory()
    view = DummyView(org_id=org.id)

    # Owner
    req = rf.get("/")
    req.user = owner
    assert IsInOrg().has_permission(req, view) is True
    assert IsOrgStaff().has_permission(req, view) is True
    assert IsOrgManager().has_permission(req, view) is True
    assert IsOrgOwner().has_permission(req, view) is True

    # Manager
    req.user = manager
    assert IsInOrg().has_permission(req, view) is True
    assert IsOrgStaff().has_permission(req, view) is True
    assert IsOrgManager().has_permission(req, view) is True
    assert IsOrgOwner().has_permission(req, view) is False

    # Staff
    req.user = staff
    assert IsInOrg().has_permission(req, view) is True
    assert IsOrgStaff().has_permission(req, view) is True
    assert IsOrgManager().has_permission(req, view) is False
    assert IsOrgOwner().has_permission(req, view) is False

    # Outsider
    req.user = outsider
    assert IsInOrg().has_permission(req, view) is False
    assert IsOrgStaff().has_permission(req, view) is False
    assert IsOrgManager().has_permission(req, view) is False
    assert IsOrgOwner().has_permission(req, view) is False


def test_org_scoped_queryset_filters_outside_org_data():
    owner = create_user("o@example.com", "o")
    u1 = create_user("u1@example.com", "u1")
    u2 = create_user("u2@example.com", "u2")
    u3 = create_user("u3@example.com", "u3")
    org_a = VendorOrg.objects.create(name="A", slug="a", owner=owner)
    org_b = VendorOrg.objects.create(name="B", slug="b", owner=owner)

    VendorMember.objects.create(org=org_a, user=owner, role=VendorMember.Role.OWNER)
    VendorMember.objects.create(org=org_a, user=u1, role=VendorMember.Role.STAFF)
    VendorMember.objects.create(org=org_a, user=u2, role=VendorMember.Role.MANAGER)
    VendorMember.objects.create(org=org_b, user=owner, role=VendorMember.Role.OWNER)
    VendorMember.objects.create(org=org_b, user=u3, role=VendorMember.Role.STAFF)

    qs = VendorMember.objects.all()
    scoped = org_scoped_queryset(qs, org_id=org_a.id)

    assert scoped.count() == 3
    assert set(scoped.values_list("org_id", flat=True)) == {org_a.id}

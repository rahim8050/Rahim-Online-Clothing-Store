import pytest
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from users.constants import VENDOR_STAFF
from users.services import deactivate_vendor_staff
from users.models import VendorStaff


@pytest.fixture
def user_factory():
    User = get_user_model()
    counter = 0

    def make_user(**kwargs):
        nonlocal counter
        counter += 1
        username = kwargs.pop("username", f"user{counter}")
        email = kwargs.pop("email", f"user{counter}@example.com")
        user = User.objects.create_user(username=username, email=email, password="pass")
        return user

    return make_user


@pytest.fixture
def vendor_staff_factory():
    def make_vs(owner, staff, **kwargs):
        defaults = {"is_active": True}
        defaults.update(kwargs)
        return VendorStaff.objects.create(owner=owner, staff=staff, **defaults)

    return make_vs


@pytest.mark.django_db
def test_revoking_last_membership_removes_group(user_factory, vendor_staff_factory):
    staff = user_factory()
    g = Group.objects.get_or_create(name=VENDOR_STAFF)[0]
    staff.groups.add(g)
    m = vendor_staff_factory(owner=user_factory(), staff=staff, is_active=True)

    deactivate_vendor_staff(m)
    staff.refresh_from_db()
    assert not staff.vendor_staff_memberships.filter(is_active=True).exists()
    assert not staff.groups.filter(name=VENDOR_STAFF).exists()

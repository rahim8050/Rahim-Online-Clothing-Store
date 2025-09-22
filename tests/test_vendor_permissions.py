import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from product_app.models import Category
from users.constants import VENDOR
from users.models import VendorStaff


@pytest.fixture
def user_factory(db):
    User = get_user_model()
    counter = {"i": 0}

    def make(**kwargs):
        counter["i"] += 1
        username = kwargs.pop("username", f"u{counter['i']}")
        email = kwargs.pop("email", f"u{counter['i']}@example.com")
        password = kwargs.pop("password", "pass")
        return User.objects.create_user(username=username, email=email, password=password, **kwargs)

    return make


@pytest.fixture
def as_login_client(client):
    def _login(u):
        client.force_login(u)
        return client

    return _login


@pytest.mark.django_db
def test_staff_cannot_remove_staff(user_factory, as_login_client):
    # Setup owner and staff users
    owner = user_factory()
    staff1 = user_factory()
    staff2 = user_factory()
    # Owner group (optional) and memberships
    Group.objects.get_or_create(name=VENDOR)[0].user_set.add(owner)
    VendorStaff.objects.create(owner=owner, staff=staff1, is_active=True)
    VendorStaff.objects.create(owner=owner, staff=staff2, is_active=True)

    c = as_login_client(staff1)
    url = reverse("vendor-staff-remove", kwargs={"staff_id": staff2.id})
    res = c.post(
        url,
        data=json.dumps({"staff_id": staff2.id, "owner_id": owner.id}),
        content_type="application/json",
    )
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_owner_can_remove_staff(user_factory, as_login_client):
    owner = user_factory()
    staff = user_factory()
    Group.objects.get_or_create(name=VENDOR)[0].user_set.add(owner)
    VendorStaff.objects.create(owner=owner, staff=staff, is_active=True)

    c = as_login_client(owner)
    url = reverse("vendor-staff-remove", kwargs={"staff_id": staff.id})
    res = c.post(
        url,
        data=json.dumps({"staff_id": staff.id, "owner_id": owner.id}),
        content_type="application/json",
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True


@pytest.mark.django_db
def test_staff_can_create_product(user_factory, as_login_client):
    owner = user_factory()
    staff = user_factory()
    Group.objects.get_or_create(name=VENDOR)[0].user_set.add(owner)
    VendorStaff.objects.create(owner=owner, staff=staff, is_active=True)

    # Minimal product prerequisites
    cat = Category.objects.create(name="Tops", slug="tops")

    c = as_login_client(staff)
    url = reverse("vendor-product-create")
    payload = {
        "name": "Staff Shirt",
        "slug": "staff-shirt-1",
        "description": "",
        "price": "10.00",
        "available": True,
        "category": cat.id,
        "owner_id": owner.id,
    }
    res = c.post(url, data=json.dumps(payload), content_type="application/json")
    assert res.status_code == 201, res.content


@pytest.mark.django_db
def test_csv_export_import_scope_gating(user_factory, as_login_client):
    owner = user_factory()
    staff_ok = user_factory()
    staff_no = user_factory()
    Group.objects.get_or_create(name=VENDOR)[0].user_set.add(owner)
    VendorStaff.objects.create(
        owner=owner, staff=staff_ok, is_active=True, scopes=["catalog"]
    )  # has catalog scope
    VendorStaff.objects.create(owner=owner, staff=staff_no, is_active=True, scopes=[])  # no scope

    # Export: owner ok
    c = as_login_client(owner)
    res = c.get(reverse("vendor-products-export-csv") + f"?owner_id={owner.id}")
    assert res.status_code == 200

    # Export: staff with scope ok
    c = as_login_client(staff_ok)
    res = c.get(reverse("vendor-products-export-csv") + f"?owner_id={owner.id}")
    assert res.status_code == 200

    # Export: staff without scope forbidden
    c = as_login_client(staff_no)
    res = c.get(reverse("vendor-products-export-csv") + f"?owner_id={owner.id}")
    assert res.status_code in (401, 403)

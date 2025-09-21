from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from orders.models import Delivery, Order
from users.constants import DRIVER, VENDOR, VENDOR_STAFF

User = get_user_model()


def mk_user(prefix):
    suf = uuid4().hex[:6]
    return User.objects.create_user(
        username=f"{prefix}{suf}", email=f"{prefix}{suf}@t.local", password="x"
    )


@pytest.mark.django_db
def test_idempotent_accept_assign_unassign_status(client):
    # users & groups
    owner = mk_user("owner")
    staff = mk_user("staff")
    driver = mk_user("driver")

    Group.objects.get_or_create(name=DRIVER)[0].user_set.add(driver)
    vg, _ = Group.objects.get_or_create(name=VENDOR)
    vsg, _ = Group.objects.get_or_create(name=VENDOR_STAFF)
    staff.groups.add(vg, vsg)

    # order + delivery (pending)
    order = Order.objects.create(
        full_name="X",
        email=f"c{uuid4().hex[:6]}@t.local",
        address="addr",
        dest_address_text="dest",
        dest_lat=0,
        dest_lng=0,
        user=owner,
    )
    d = Delivery.objects.create(order=order, dest_lat=0, dest_lng=0, status=Delivery.Status.PENDING)

    # Accept is idempotent for the same driver:
    client.force_login(driver)
    r1 = client.post(f"/apis/deliveries/{d.id}/accept/")
    assert r1.status_code == 200
    d.refresh_from_db()
    assigned_at_1 = d.assigned_at
    assert d.driver_id == driver.id and d.status == Delivery.Status.ASSIGNED

    # repeat accept → 200 and assigned_at unchanged
    r2 = client.post(f"/apis/deliveries/{d.id}/accept/")
    assert r2.status_code == 200
    d.refresh_from_db()
    assert d.assigned_at == assigned_at_1

    # Status picked_up is idempotent (re-post doesn't bump timestamp)
    r3 = client.post(f"/apis/deliveries/{d.id}/status/", {"status": Delivery.Status.PICKED_UP})
    assert r3.status_code == 200
    d.refresh_from_db()
    ts1 = d.picked_up_at
    assert ts1 is not None

    r4 = client.post(f"/apis/deliveries/{d.id}/status/", {"status": Delivery.Status.PICKED_UP})
    assert r4.status_code == 200
    d.refresh_from_db()
    assert d.picked_up_at == ts1  # unchanged

    # Vendor unassign is idempotent
    client.logout()
    client.force_login(staff)
    u1 = client.post(f"/apis/deliveries/{d.id}/unassign/")
    assert u1.status_code == 200
    d.refresh_from_db()
    assert d.driver_id is None and d.status == Delivery.Status.PENDING and d.assigned_at is None

    u2 = client.post(f"/apis/deliveries/{d.id}/unassign/")  # repeat
    assert u2.status_code == 200
    d.refresh_from_db()
    assert d.driver_id is None and d.status == Delivery.Status.PENDING and d.assigned_at is None

    # Vendor re-assign same driver → idempotent
    a1 = client.post(f"/apis/deliveries/{d.id}/assign/", {"driver_id": driver.id})
    assert a1.status_code == 200
    d.refresh_from_db()
    a_at = d.assigned_at
    assert d.driver_id == driver.id and d.status == Delivery.Status.ASSIGNED

    a2 = client.post(f"/apis/deliveries/{d.id}/assign/", {"driver_id": driver.id})
    assert a2.status_code == 200
    d.refresh_from_db()
    assert d.assigned_at == a_at  # unchanged

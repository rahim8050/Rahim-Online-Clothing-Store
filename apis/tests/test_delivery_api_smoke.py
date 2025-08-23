import pytest
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from orders.models import Delivery, Order
from users.constants import VENDOR, VENDOR_STAFF, DRIVER

User = get_user_model()

@pytest.mark.django_db
def test_assign_and_status(client):
    suf = uuid4().hex[:6]

    owner  = User.objects.create_user(username=f"owner_{suf}",  email=f"owner_{suf}@test.local",  password="x")
    staff  = User.objects.create_user(username=f"staff_{suf}",  email=f"staff_{suf}@test.local",  password="x")
    driver = User.objects.create_user(username=f"driver_{suf}", email=f"driver_{suf}@test.local", password="x")

    # Put staff into vendor + vendor_staff; driver into driver group
    vendor_group, _ = Group.objects.get_or_create(name=VENDOR)
    vendor_staff_group, _ = Group.objects.get_or_create(name=VENDOR_STAFF)
    staff.groups.add(vendor_group, vendor_staff_group)
    driver_group, _ = Group.objects.get_or_create(name=DRIVER)
    driver.groups.add(driver_group)

    order = Order.objects.create(
        full_name="X", email=f"cust_{suf}@test.local", address="addr",
        dest_address_text="dest", dest_lat=0, dest_lng=0, user=owner
    )
    d = Delivery.objects.create(order=order, status=Delivery.Status.PENDING, dest_lat=0, dest_lng=0)

    # Vendor assigns the driver
    client.force_login(staff)
    resp = client.post(
        f"/apis/deliveries/{d.pk}/assign/",
        data={"driver_id": driver.id},
        content_type="application/json",
    )
    assert resp.status_code in (200, 201)
    d.refresh_from_db()
    assert d.driver_id == driver.id
    assert d.status == Delivery.Status.ASSIGNED

    # Driver updates status
    client.logout()
    client.force_login(driver)
    resp = client.post(
        f"/apis/deliveries/{d.pk}/status/",
        data={"status": Delivery.Status.PICKED_UP},
        content_type="application/json",
    )
    assert resp.status_code == 200
    d.refresh_from_db()
    assert d.status == Delivery.Status.PICKED_UP
    assert d.picked_up_at is not None

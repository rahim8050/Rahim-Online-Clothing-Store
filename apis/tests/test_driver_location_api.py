from uuid import uuid4

import pytest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from orders.models import Delivery, Order
from users.constants import DRIVER

User = get_user_model()

@pytest.mark.django_db
def test_driver_location_persists_and_publishes(client, monkeypatch):
    suf = uuid4().hex[:6]
    owner = User.objects.create_user(username=f"o{suf}", email=f"o{suf}@t.local", password="x")
    driver = User.objects.create_user(username=f"d{suf}", email=f"d{suf}@t.local", password="x")
    Group.objects.get_or_create(name=DRIVER)[0].user_set.add(driver)

    order = Order.objects.create(
        full_name="X",
        email=f"c{suf}@t.local",
        address="addr",
        dest_address_text="dest",
        dest_lat=0,
        dest_lng=0,
        user=owner,
    )
    d = Delivery.objects.create(
        order=order,
        dest_lat=0,
        dest_lng=0,
        status=Delivery.Status.ASSIGNED,
        driver=driver,
    )

    called = {}
    # monkeypatch the publisher in this module
    import apis.views as v

    def fake_publish(delivery, kind, payload=None):
        called["kind"] = kind
        called["payload"] = payload or {}
        called["id"] = delivery.id

    monkeypatch.setattr(v, "_publish_delivery", fake_publish)

    client.force_login(driver)
    resp = client.post(
        "/apis/driver/location/",
        data={"delivery_id": d.id, "lat": -1.29, "lng": 36.82},
        content_type="application/json",
    )
    assert resp.status_code == 200
    d.refresh_from_db()
    assert d.last_lat == -1.29 and d.last_lng == 36.82 and d.last_ping_at is not None
    assert called["kind"] == "position" and called["id"] == d.id

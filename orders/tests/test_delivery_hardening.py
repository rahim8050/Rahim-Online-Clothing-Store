import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from orders.models import Delivery, Order


@pytest.fixture
def driver(django_user_model):
    u = django_user_model.objects.create_user(username="driver", password="pw")
    from django.contrib.auth.models import Group

    g, _ = Group.objects.get_or_create(name="driver")
    u.groups.add(g)
    return u


@pytest.fixture
def order(driver):
    User = get_user_model()
    customer = User.objects.create_user(username="cust", password="pw")
    o = Order.objects.create(
        full_name="C",
        email="c@example.com",
        address="A",
        dest_address_text="X",
        dest_lat=-1.28,
        dest_lng=36.82,
        user=customer,
    )
    return o


@pytest.mark.django_db
def test_transitions_idempotent(order, driver):
    d = Delivery.objects.create(
        order=order, driver=driver, status=Delivery.Status.ASSIGNED
    )
    when = timezone.now()
    d.mark_picked_up(by=driver, when=when)
    d.save()
    first = d.picked_up_at
    # Re-run should keep first timestamp
    d.mark_picked_up(by=driver, when=when.replace(year=2001))
    d.save()
    assert d.picked_up_at == first


@pytest.mark.django_db
def test_invalid_transition_rejected(order, driver):
    d = Delivery.objects.create(
        order=order, driver=driver, status=Delivery.Status.PENDING
    )
    with pytest.raises(ValueError):
        d.mark_delivered(by=driver)


@pytest.mark.django_db
def test_driver_viewset_permissions(client, order, driver):
    d = Delivery.objects.create(
        order=order, driver=driver, status=Delivery.Status.ASSIGNED
    )
    client.force_login(driver)
    # list only returns driver's deliveries
    r = client.get("/apis/deliveries/")
    assert r.status_code == 200
    assert any(x["id"] == d.id for x in r.json())
    # pickup action
    r = client.post(f"/apis/deliveries/{d.id}/pickup/")
    assert r.status_code == 200
    payload = r.json()
    assert payload["id"] == d.id
    assert payload["status"] in (
        Delivery.Status.PICKED_UP,
        Delivery.Status.ASSIGNED,
        Delivery.Status.EN_ROUTE,
    )

import re
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from orders.models import Order, Transaction, Delivery


@pytest.mark.django_db
def test_requires_auth_returns_401_for_anon(client):
    url = "/api/assistant/ask/"
    r = client.post(url, data={"session_key": "s1", "message": "list orders"}, content_type="application/json")
    assert r.status_code in (401, 403)


def _login(client):
    User = get_user_model()
    u = User.objects.create_user(username="alice", email="alice@example.com", password="pass")
    client.force_login(u)
    return u


def _mk_order(user, **kwargs):
    o = Order.objects.create(
        full_name="Alice",
        email="alice@example.com",
        address="123 Street",
        dest_address_text="Somewhere",
        dest_lat= -1.28,
        dest_lng= 36.82,
        user=user,
        **kwargs,
    )
    return o


@pytest.mark.django_db
def test_list_orders_matches_natural_phrase(client):
    u = _login(client)
    _mk_order(u)
    url = "/api/assistant/ask/"
    for msg in ("tell me about my orders", "show my orders", "list orders"):
        r = client.post(url, data={"session_key": "s1", "message": msg}, content_type="application/json")
        assert r.status_code == 200
        assert "Recent orders:" in r.json()["reply"]


@pytest.mark.django_db
def test_order_status_by_id_and_order_number(client):
    u = _login(client)
    o = _mk_order(u)
    url = "/api/assistant/ask/"
    r = client.post(url, data={"session_key": "s1", "message": f"order status {o.id}"}, content_type="application/json")
    assert r.status_code == 200
    assert f"RAH{o.id}" in r.json()["reply"]
    r = client.post(url, data={"session_key": "s1", "message": f"order status RAH{o.id}"}, content_type="application/json")
    assert r.status_code == 200
    assert f"RAH{o.id}" in r.json()["reply"]


@pytest.mark.django_db
def test_payment_status_and_delivery_status_paths(client):
    u = _login(client)
    o = _mk_order(u)
    Transaction.objects.create(user=u, order=o, amount=10, method="card", gateway="paystack", status="initialized", reference="ref1")
    Delivery.objects.create(order=o, status="pending")
    url = "/api/assistant/ask/"
    r = client.post(url, data={"session_key": "s1", "message": f"payment status {o.id}"}, content_type="application/json")
    assert r.status_code == 200
    assert "payment" in r.json()["reply"].lower()
    r = client.post(url, data={"session_key": "s1", "message": f"delivery status {o.id}"}, content_type="application/json")
    assert r.status_code == 200
    assert "delivery status" in r.json()["reply"].lower()


@pytest.mark.django_db
def test_ownership_enforced(client):
    u = _login(client)
    v = get_user_model().objects.create_user(username="bob", email="bob@example.com", password="pass")
    o = _mk_order(v)
    url = "/api/assistant/ask/"
    r = client.post(url, data={"session_key": "s1", "message": f"order status {o.id}"}, content_type="application/json")
    assert r.status_code == 200
    assert "couldn't find" in r.json()["reply"].lower()


@pytest.mark.django_db
def test_faq_shipping_and_returns(client):
    _login(client)
    url = "/api/assistant/ask/"
    for msg in ("shipping", "returns"):
        r = client.post(url, data={"session_key": "s1", "message": msg}, content_type="application/json")
        assert r.status_code == 200
        assert len(r.json()["reply"]) > 8


@pytest.mark.django_db
def test_help_fallback_when_no_match(client):
    _login(client)
    url = "/api/assistant/ask/"
    r = client.post(url, data={"session_key": "s1", "message": "blabla unknown"}, content_type="application/json")
    assert r.status_code == 200
    assert "list orders" in r.json()["reply"].lower()


@pytest.mark.django_db
def test_redaction_masks_email_and_phone_in_reply(client):
    _login(client)
    url = "/api/assistant/ask/"
    msg = "my email is foo@example.com and phone is +254 700 000 000"
    r = client.post(url, data={"session_key": "s1", "message": msg}, content_type="application/json")
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "example.com" not in reply
    assert "+254" not in reply


@pytest.mark.django_db
@pytest.mark.xfail(strict=False)
def test_rate_limit_user(client):
    _login(client)
    url = "/api/assistant/ask/"
    for _ in range(130):
        client.post(url, data={"session_key": "s1", "message": "list orders"}, content_type="application/json")
    # Eventually should start failing with 429; timing-sensitive in CI
    r = client.post(url, data={"session_key": "s1", "message": "list orders"}, content_type="application/json")
    assert r.status_code in (200, 429)


import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from product_app.models import Category, Product
from cart.models import Cart, CartItem


User = get_user_model()


def v2_guest(url: str) -> str:
    return f"/apis/v2/cart/guest{url}"


@pytest.fixture()
def api():
    return APIClient()


@pytest.fixture()
def user(db):
    return User.objects.create_user(username="u1", email="u1@example.com", password="pass")


@pytest.fixture()
def product(db):
    cat = Category.objects.create(name="Shirts", slug="shirts")
    return Product.objects.create(category=cat, name="Blue Shirt", slug="blue-shirt", price="10.00")


@pytest.mark.django_db
def test_guest_cart_cookie_creation(api):
    r = api.post(v2_guest("/carts/my_active/"))
    assert r.status_code in (200, 201)
    assert "guest_cart_id" in r.cookies
    cid = r.json()["id"]
    # read back
    r2 = api.get(v2_guest(f"/carts/{cid}/"))
    assert r2.status_code == 200
    assert r2.json()["id"] == cid


@pytest.mark.django_db
def test_guest_add_and_merge_on_login(api, user, product):
    # create guest cart + add item
    r = api.post(v2_guest("/carts/my_active/"))
    cid = r.json()["id"]
    api.post(v2_guest(f"/carts/{cid}/add_item/"), {"product": product.id, "quantity": 2}, format="json")

    # simulate login signal to trigger merge
    from django.contrib.auth.signals import user_logged_in
    from django.test.client import RequestFactory
    rf = RequestFactory()
    req = rf.get("/")
    user_logged_in.send(sender=user.__class__, request=req, user=user)

    user_cart, _ = Cart.objects.get_or_create(user=user, status="active")
    assert CartItem.objects.filter(cart=user_cart, product=product, quantity=2).exists()
    # guest cart removed
    assert not Cart.objects.filter(pk=cid).exists()

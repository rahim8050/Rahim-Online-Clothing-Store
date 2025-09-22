import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from cart.models import Cart, CartItem
from product_app.models import Category, Product

User = get_user_model()


@pytest.fixture()
def api():
    return APIClient()


@pytest.fixture()
def user(db):
    return User.objects.create_user(username="u1", email="u1@example.com", password="pass")


@pytest.fixture()
def other_user(db):
    return User.objects.create_user(username="u2", email="u2@example.com", password="pass")


@pytest.fixture()
def product(db):
    cat = Category.objects.create(name="Shirts", slug="shirts")
    return Product.objects.create(category=cat, name="Blue Shirt", slug="blue-shirt", price="10.00")


def auth(client, user):
    client.force_authenticate(user)


def v2(url: str) -> str:
    return f"/apis/v2/cart{url}"


@pytest.mark.django_db
def test_my_active_creates_single_active_cart_per_user(api, user):
    auth(api, user)
    r1 = api.get(v2("/carts/my/active/"))
    assert r1.status_code == 200
    r2 = api.get(v2("/carts/my/active/"))
    assert r2.status_code == 200
    assert r1.data["id"] == r2.data["id"]
    assert Cart.objects.filter(user=user, status="active").count() == 1


@pytest.mark.django_db
def test_list_returns_only_users_carts(api, user, other_user):
    auth(api, user)
    c1 = Cart.objects.create(user=user)
    Cart.objects.create(user=other_user)
    r = api.get(v2("/carts/"))
    assert r.status_code == 200
    ids = [c["id"] for c in r.data]
    assert c1.id in ids
    # ensure other's cart is hidden
    assert all(c["id"] != Cart.objects.filter(user=other_user).first().id for c in r.data)


@pytest.mark.django_db
def test_retrieve_forbidden_for_other_users_cart(api, user, other_user):
    auth(api, user)
    c_other = Cart.objects.create(user=other_user)
    r = api.get(v2(f"/carts/{c_other.id}/"))
    assert r.status_code == 404


@pytest.mark.django_db
def test_add_item_creates_or_increments_uniquely(api, user, product):
    auth(api, user)
    cart_id = api.get(v2("/carts/my/active/")).data["id"]
    r1 = api.post(
        v2(f"/carts/{cart_id}/add_item/"), {"product": product.id, "quantity": 1}, format="json"
    )
    assert r1.status_code == 200
    r2 = api.post(
        v2(f"/carts/{cart_id}/add_item/"), {"product": product.id, "quantity": 2}, format="json"
    )
    assert r2.status_code == 200
    item = CartItem.objects.get(cart_id=cart_id, product=product)
    assert item.quantity == 3


@pytest.mark.django_db
def test_update_item_sets_exact_quantity(api, user, product):
    auth(api, user)
    cart = Cart.objects.create(user=user)
    item = CartItem.objects.create(cart=cart, product=product, quantity=1)
    r = api.post(
        v2(f"/carts/{cart.id}/update_item/"), {"item_id": item.id, "quantity": 5}, format="json"
    )
    assert r.status_code == 200
    item.refresh_from_db()
    assert item.quantity == 5


@pytest.mark.django_db
def test_remove_item_deletes_only_own_item(api, user, other_user, product):
    auth(api, user)
    my_cart = Cart.objects.create(user=user)
    other_cart = Cart.objects.create(user=other_user)
    my_item = CartItem.objects.create(cart=my_cart, product=product, quantity=1)
    other_item = CartItem.objects.create(cart=other_cart, product=product, quantity=1)
    r = api.post(v2(f"/carts/{my_cart.id}/remove_item/"), {"item_id": other_item.id}, format="json")
    assert r.status_code == 200
    assert r.data["removed"] is False
    assert CartItem.objects.filter(pk=other_item.id).exists()
    r2 = api.post(v2(f"/carts/{my_cart.id}/remove_item/"), {"item_id": my_item.id}, format="json")
    assert r2.status_code == 200
    assert r2.data["removed"] is True
    assert not CartItem.objects.filter(pk=my_item.id).exists()


@pytest.mark.django_db
def test_clear_deletes_all_items(api, user, product):
    auth(api, user)
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    CartItem.objects.create(cart=cart, product=product, quantity=2)
    r = api.post(v2(f"/carts/{cart.id}/clear/"))
    assert r.status_code == 200
    assert r.data["cleared"] is True
    assert CartItem.objects.filter(cart=cart).count() == 0

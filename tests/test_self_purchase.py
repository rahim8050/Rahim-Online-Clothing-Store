import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from cart.models import Cart, CartItem
from orders.services import create_order_from_cart
from product_app.models import Category, Product
from users.constants import VENDOR, VENDOR_STAFF
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
def category():
    return Category.objects.create(name="Cat", slug="cat")


@pytest.fixture
def product_factory(category):
    counter = 0

    def make_product(owner, **kwargs):
        nonlocal counter
        counter += 1
        defaults = {
            "name": f"Prod {counter}",
            "slug": f"prod-{counter}",
            "price": 10,
            "category": category,
            "owner": owner,
        }
        defaults.update(kwargs)
        return Product.objects.create(**defaults)

    return make_product


@pytest.fixture
def cart_factory():
    def make_cart(user, items):
        cart = Cart.objects.create()
        for product, qty in items:
            CartItem.objects.create(cart=cart, product=product, quantity=qty)
        return cart

    return make_cart


@pytest.fixture
def vendor_staff_factory():
    def make_vs(owner, staff, **kwargs):
        defaults = {"is_active": True}
        defaults.update(kwargs)
        return VendorStaff.objects.create(owner=owner, staff=staff, **defaults)

    return make_vs


@pytest.mark.django_db
def test_vendor_cannot_buy_own_listing(user_factory, product_factory, cart_factory):
    vendor = user_factory()
    Group.objects.get_or_create(name=VENDOR)[0].user_set.add(vendor)
    product = product_factory(owner=vendor)
    cart = cart_factory(user=vendor, items=[(product, 1)])
    with pytest.raises(PermissionError):
        create_order_from_cart(vendor, cart)


@pytest.mark.django_db
def test_vendor_staff_cannot_buy_owner_listing(
    user_factory, product_factory, cart_factory, vendor_staff_factory
):
    owner = user_factory()
    staff = user_factory()
    Group.objects.get_or_create(name=VENDOR_STAFF)[0].user_set.add(staff)
    vendor_staff_factory(owner=owner, staff=staff, is_active=True)
    product = product_factory(owner=owner)
    cart = cart_factory(user=staff, items=[(product, 1)])
    with pytest.raises(PermissionError):
        create_order_from_cart(staff, cart)

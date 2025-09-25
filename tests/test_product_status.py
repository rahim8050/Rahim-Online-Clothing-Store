from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from product_app.models import Category, Product


@pytest.mark.django_db
def test_product_status_default_model():
    cat = Category.objects.create(name="Cat", slug="cat")
    p = Product.objects.create(
        category=cat, name="X", slug="x-1", price=Decimal("1.00")
    )
    assert p.status in (Product.Status.ACTIVE, "active")


@pytest.mark.django_db
def test_admin_add_product_uses_default_status(client):
    User = get_user_model()
    admin = User.objects.create_superuser("admin", "admin@example.com", "pass")
    client.force_login(admin)
    cat = Category.objects.create(name="Cat2", slug="cat2")
    url = reverse("admin:product_app_product_add")
    form = {
        "category": cat.id,
        "name": "Y",
        "slug": "y-1",
        "price": "2.00",
        "available": "on",
        "_save": "Save",
    }
    r = client.post(url, form, follow=True)
    assert r.status_code == 200
    p = Product.objects.get(slug="y-1")
    assert p.status in (Product.Status.ACTIVE, "active")

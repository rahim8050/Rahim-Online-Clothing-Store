from decimal import Decimal

import pytest

from product_app.models import Category, Product


@pytest.mark.django_db
def test_version_default_on_create():
    cat = Category.objects.create(name="C", slug="c")
    p = Product.objects.create(category=cat, name="X", slug="x-ver", price=Decimal("1.00"))
    assert p.version == 1

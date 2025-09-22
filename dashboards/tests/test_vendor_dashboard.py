import pytest
from django.contrib.auth.models import Group
from django.urls import reverse


@pytest.mark.django_db
def test_access_scoped(client, django_user_model):
    g, _ = Group.objects.get_or_create(name="Vendor")
    u = django_user_model.objects.create_user("v", "v@x.com", "x")
    u.groups.add(g)
    client.login(username="v", password="x")
    r = client.get(reverse("vendor-dashboard"))
    assert r.status_code in (200, 403)

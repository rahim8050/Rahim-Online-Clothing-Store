import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_vendor_applications_deprecated(client, django_user_model):
    u = django_user_model.objects.create_user(username="u1", email="u1@example.com", password="pass")
    client.force_login(u)
    url = reverse("users:vendor-apply")
    res = client.get(url)
    assert res.status_code in (301, 302, 307)
    assert "/apis/vendor/apply/" in (res.headers.get("Location") or "")
    assert res.headers.get("Deprecation") == "true"

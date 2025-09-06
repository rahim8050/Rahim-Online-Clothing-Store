from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

from users.permissions import IsVendorOrVendorStaff


def test_is_vendor_or_staff_allows_vendor_group(db):
    User = get_user_model()
    u = User.objects.create_user(username="v", password="p")
    g, _ = Group.objects.get_or_create(name="Vendor")
    g.user_set.add(u)

    class DummyReq:
        user = u

    assert IsVendorOrVendorStaff().has_permission(DummyReq(), None) is True


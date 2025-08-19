from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import VendorStaff
from users.services.vendor_staff import TOKEN_SALT


@override_settings(ROOT_URLCONF="apis.urls")
class VendorStaffAcceptTests(TestCase):
    def _create_vs(self):
        User = get_user_model()
        owner = User.objects.create_user(
            username="owner", password="pwd", email="o@example.com"
        )
        staff = User.objects.create_user(
            username="staff", password="pwd", email="s@example.com"
        )
        vs = VendorStaff.objects.create(owner=owner, staff=staff)
        return owner, staff, vs

    def test_accept_happy(self):
        owner, staff, vs = self._create_vs()
        token = signing.dumps({"vs_id": vs.id, "staff_id": staff.id}, salt=TOKEN_SALT)
        self.client.force_login(staff)
        resp = self.client.post(reverse("vendor-staff-accept", args=[token]))
        self.assertEqual(resp.status_code, 200)
        vs.refresh_from_db()
        self.assertEqual(vs.status, "accepted")

    def test_accept_expired_token(self):
        owner, staff, vs = self._create_vs()
        with patch("django.core.signing.time.time", return_value=0):
            token = signing.dumps({"vs_id": vs.id, "staff_id": staff.id}, salt=TOKEN_SALT)
        self.client.force_login(staff)
        resp = self.client.post(reverse("vendor-staff-accept", args=[token]))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["message"], "token expired")
        vs.refresh_from_db()
        self.assertEqual(vs.status, "pending")

    def test_accept_invalid_signature(self):
        owner, staff, vs = self._create_vs()
        token = signing.dumps({"vs_id": vs.id, "staff_id": staff.id}, salt=TOKEN_SALT)
        bad_token = token + "x"
        self.client.force_login(staff)
        resp = self.client.post(reverse("vendor-staff-accept", args=[bad_token]))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["message"], "invalid token")
        vs.refresh_from_db()
        self.assertEqual(vs.status, "pending")

    def test_accept_replay(self):
        owner, staff, vs = self._create_vs()
        token = signing.dumps({"vs_id": vs.id, "staff_id": staff.id}, salt=TOKEN_SALT)
        self.client.force_login(staff)
        url = reverse("vendor-staff-accept", args=[token])
        resp1 = self.client.post(url)
        self.assertEqual(resp1.status_code, 200)
        vs.refresh_from_db()
        self.assertEqual(vs.status, "accepted")
        resp2 = self.client.post(url)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["message"], "already accepted")
        vs.refresh_from_db()
        self.assertEqual(vs.status, "accepted")

    def test_accept_user_mismatch(self):
        User = get_user_model()
        owner = User.objects.create_user(
            username="owner", password="pwd", email="o@example.com"
        )
        staff = User.objects.create_user(
            username="staff", password="pwd", email="s@example.com"
        )
        other = User.objects.create_user(
            username="other", password="pwd", email="x@example.com"
        )
        vs = VendorStaff.objects.create(owner=owner, staff=staff)
        token = signing.dumps({"vs_id": vs.id, "staff_id": staff.id}, salt=TOKEN_SALT)
        self.client.force_login(other)
        resp = self.client.post(reverse("vendor-staff-accept", args=[token]))
        self.assertEqual(resp.status_code, 403)
        vs.refresh_from_db()
        self.assertEqual(vs.status, "pending")

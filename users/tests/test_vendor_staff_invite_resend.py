from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from users.models import VendorStaff


@override_settings(ROOT_URLCONF="apis.urls")
class VendorStaffInviteResendTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner", password="pwd", email="o@example.com"
        )
        self.staff = User.objects.create_user(
            username="staff", password="pwd", email="s@example.com"
        )
        vendor_group, _ = Group.objects.get_or_create(name="Vendor")
        vendor_group.user_set.add(self.owner)
        self.client.force_login(self.owner)

    @patch("users.services.vendor_staff.EmailMultiAlternatives.send", return_value=0)
    def test_invite_resend_requires_flag(self, mock_send):
        url = reverse("vendor-staff-invite")
        resp1 = self.client.post(
            url, {"staff_id": self.staff.id, "owner_id": self.owner.id}
        )
        self.assertEqual(resp1.status_code, 201)

        resp2 = self.client.post(
            url, {"staff_id": self.staff.id, "owner_id": self.owner.id}
        )
        self.assertEqual(resp2.status_code, 200)
        data = resp2.json()
        self.assertFalse(data["emailed"])
        self.assertIn("pending", data["message"].lower())

    @patch("users.services.vendor_staff.EmailMultiAlternatives.send", return_value=0)
    def test_invite_resend_cooldown_blocks(self, mock_send):
        VendorStaff.objects.create(
            owner=self.owner,
            staff=self.staff,
            status="pending",
            last_emailed_at=timezone.now(),
        )
        url = reverse("vendor-staff-invite") + "?resend=1"
        resp = self.client.post(
            url, {"staff_id": self.staff.id, "owner_id": self.owner.id}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["emailed"])
        self.assertIn("cooldown", data["message"].lower())

    @patch("users.services.vendor_staff.EmailMultiAlternatives.send", return_value=0)
    def test_invite_resend_after_cooldown_succeeds(self, mock_send):
        VendorStaff.objects.create(
            owner=self.owner,
            staff=self.staff,
            status="pending",
            last_emailed_at=timezone.now() - timedelta(minutes=10),
        )
        url = reverse("vendor-staff-invite") + "?resend=1"
        resp = self.client.post(
            url, {"staff_id": self.staff.id, "owner_id": self.owner.id}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["emailed"])

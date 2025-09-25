from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from users.constants import VENDOR, VENDOR_STAFF
from users.models import VendorStaff


class VendorStaffAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.User = get_user_model()
        # ensure groups
        self.vendor_group = Group.objects.get_or_create(name=VENDOR)[0]
        self.staff_group = Group.objects.get_or_create(name=VENDOR_STAFF)[0]

        self.owner = self.User.objects.create_user(
            username="owner", email="owner@example.com", password="pass"
        )
        self.vendor_group.user_set.add(self.owner)
        self.other_owner = self.User.objects.create_user(
            username="other", email="other@example.com", password="pass"
        )
        self.vendor_group.user_set.add(self.other_owner)
        self.staff1 = self.User.objects.create_user(
            username="staff1", email="staff1@example.com", password="pass"
        )
        self.staff2 = self.User.objects.create_user(
            username="staff2", email="staff2@example.com", password="pass"
        )

        VendorStaff.objects.create(owner=self.owner, staff=self.staff1, is_active=True)
        VendorStaff.objects.create(
            owner=self.other_owner, staff=self.staff2, is_active=True
        )

    def auth(self, user):
        self.client.force_login(user)

    def test_list_and_scope(self):
        url = reverse("vendor-staff-list")
        self.auth(self.owner)
        resp = self.client.get(url, {"owner_id": self.owner.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["staff"], self.staff1.id)

        # other owner cannot access owner's memberships
        self.auth(self.other_owner)
        resp = self.client.get(url, {"owner_id": self.owner.id})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("owner_id", resp.json())

    def test_invite_success_and_errors(self):
        url = reverse("vendor-staff-invite")
        self.auth(self.owner)
        resp = self.client.post(
            url, {"staff_id": self.staff2.id, "owner_id": self.owner.id}, format="json"
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["owner"], self.owner.id)
        self.assertEqual(data["staff"], self.staff2.id)
        self.assertTrue(data["is_active"])
        self.assertTrue(
            VendorStaff.objects.filter(
                owner=self.owner, staff=self.staff2, is_active=True
            ).exists()
        )
        self.assertTrue(self.staff2.groups.filter(name=VENDOR_STAFF).exists())

        # prevent self invite
        resp = self.client.post(
            url, {"staff_id": self.owner.id, "owner_id": self.owner.id}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("staff_id", resp.json())

        # non existent staff
        resp = self.client.post(
            url, {"staff_id": 9999, "owner_id": self.owner.id}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["staff_id"][0], "User not found.")

        # owner scope rejection
        resp = self.client.post(
            url,
            {"staff_id": self.staff2.id, "owner_id": self.other_owner.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("owner_id", resp.json())

    def test_toggle(self):
        url = reverse("vendor-staff-toggle")
        self.auth(self.owner)
        resp = self.client.patch(
            url,
            {"staff_id": self.staff1.id, "is_active": False, "owner_id": self.owner.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["is_active"])
        resp = self.client.patch(
            url,
            {"staff_id": self.staff1.id, "is_active": True, "owner_id": self.owner.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_active"])

        # missing membership
        resp = self.client.patch(
            url,
            {"staff_id": self.staff2.id, "is_active": False, "owner_id": self.owner.id},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["staff_id"], "Membership not found.")

    def test_remove(self):
        url = reverse("vendor-staff-remove")
        self.auth(self.owner)
        resp = self.client.post(
            url, {"staff_id": self.staff1.id, "owner_id": self.owner.id}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})
        membership = VendorStaff.objects.get(owner=self.owner, staff=self.staff1)
        self.assertFalse(membership.is_active)

        # idempotent / nonexistent membership
        resp = self.client.post(
            url, {"staff_id": self.staff2.id, "owner_id": self.owner.id}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})

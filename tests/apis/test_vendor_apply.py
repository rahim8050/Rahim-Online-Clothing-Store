import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import TestCase
from django.contrib.auth import get_user_model
from users.models import VendorApplication

User = get_user_model()


class VendorApplyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="x")
        self.url = reverse("apis:vendor-apply")

    def _doc(self):
        return SimpleUploadedFile("kyc.pdf", b"%PDF-1.4\n...", content_type="application/pdf")

    def test_first_apply_requires_kyc(self):
        self.client.login(username="u1", password="x")
        r = self.client.post(self.url, {})
        assert r.status_code == 400

    def test_first_apply_success(self):
        self.client.login(username="u1", password="x")
        r = self.client.post(self.url, {
            "company_name": "Acme Ltd",
            "phone": "0712345678",
            "kra_pin": "A123456789B",
            "national_id": "12345678",
            "document": self._doc(),
        })
        assert r.status_code in (200, 201)
        assert VendorApplication.objects.filter(user=self.user, status=VendorApplication.PENDING).exists()

    def test_idempotent_pending(self):
        self.client.login(username="u1", password="x")
        VendorApplication.objects.create(user=self.user, status=VendorApplication.PENDING,
                                         company_name="Acme", phone="071", kra_pin="A123456789B",
                                         national_id="1", document=self._doc())
        r = self.client.post(self.url, {
            "company_name": "Acme Ltd",
            "phone": "0712345678",
            "kra_pin": "A123456789B",
            "national_id": "12345678",
            "document": self._doc(),
        })
        assert r.status_code == 200

    def test_reapply_after_rejected_requires_kyc(self):
        self.client.login(username="u1", password="x")
        VendorApplication.objects.create(user=self.user, status=VendorApplication.REJECTED,
                                         company_name="Acme", phone="071", kra_pin="A123456789B",
                                         national_id="1", document=self._doc())
        r = self.client.post(self.url, {
            "company_name": "Acme Ltd",
            "phone": "0712345678",
            "kra_pin": "A123456789B",
            "national_id": "12345678",
            "document": self._doc(),
        })
        assert r.status_code in (200, 201)

    def test_apply_when_approved_blocks(self):
        self.client.login(username="u1", password="x")
        VendorApplication.objects.create(user=self.user, status=VendorApplication.APPROVED,
                                         company_name="Acme", phone="071", kra_pin="A123456789B",
                                         national_id="1", document=self._doc())
        r = self.client.post(self.url, {
            "company_name": "Acme Ltd",
            "phone": "0712345678",
            "kra_pin": "A123456789B",
            "national_id": "12345678",
            "document": self._doc(),
        })
        assert r.status_code == 409


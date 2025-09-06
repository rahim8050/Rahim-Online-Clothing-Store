import json
import hmac
import hashlib

from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(LEGACY_ORDER_PAYMENTS=False, PAYSTACK_SECRET_KEY="secret")
class LegacyPaymentsFlagTests(TestCase):
    def test_orders_paystack_webhook_returns_410_when_disabled(self):
        url = reverse("orders:paystack_webhook")
        event = {"data": {"reference": "ref-x", "status": "success"}}
        body = json.dumps(event)
        sig = hmac.new(b"secret", body.encode(), hashlib.sha512).hexdigest()
        r = self.client.post(url, body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig)
        self.assertEqual(r.status_code, 410)

    def test_payments_paystack_webhook_still_works(self):
        url = reverse("paystack_webhook")
        event = {"data": {"reference": "ref-x", "status": "failed"}}
        body = json.dumps(event)
        sig = hmac.new(b"secret", body.encode(), hashlib.sha512).hexdigest()
        r = self.client.post(url, body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig)
        # 202 for missing reference in DB, but endpoint reachable and signature passes
        self.assertIn(r.status_code, {200, 202})


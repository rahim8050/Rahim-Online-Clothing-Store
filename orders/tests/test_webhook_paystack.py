import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import Order, OrderItem, PaymentEvent, Transaction
from product_app.models import Category, Product, ProductStock, Warehouse


@override_settings(PAYSTACK_SECRET_KEY="sk_test_example")
class PaystackWebhookHardenedTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p", email="u@example.com")
        cat = Category.objects.create(name="c", slug="c")
        prod = Product.objects.create(category=cat, name="p", slug="p", price=10)
        wh = Warehouse.objects.create(name="w", latitude=1.0, longitude=36.0)
        ProductStock.objects.create(product=prod, warehouse=wh, quantity=5)
        self.order = Order.objects.create(
            user=self.user,
            full_name="F",
            email="u@example.com",
            address="A",
            latitude=1.0,
            longitude=36.0,
            dest_address_text="A",
            dest_lat=1.0,
            dest_lng=36.0,
        )
        OrderItem.objects.create(order=self.order, product=prod, price=10, quantity=1, warehouse=wh)
        self.tx = Transaction.objects.create(
            user=self.user,
            order=self.order,
            email=self.user.email,
            amount=10,
            method="card",
            gateway="paystack",
            status="pending",
            reference="ref_123",
        )

    def _sign(self, body: bytes) -> str:
        return hmac.new(b"sk_test_example", body, hashlib.sha512).hexdigest()

    def test_webhook_valid_signature_returns_200_and_creates_transaction(self):
        body = json.dumps(
            {
                "event": "charge.success",
                "data": {"reference": self.tx.reference, "metadata": {"order_id": self.order.id}},
            },
            separators=(",", ":"),
        ).encode()
        sig = self._sign(body)
        resp = self.client.post(
            reverse("orders:paystack_webhook"),
            body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig,
        )
        self.assertEqual(resp.status_code, 200)
        self.tx.refresh_from_db()
        self.order.refresh_from_db()
        self.assertTrue(self.tx.callback_received)
        self.assertTrue(self.tx.verified)
        self.assertEqual(self.tx.status, "success")
        self.assertTrue(PaymentEvent.objects.filter(reference=self.tx.reference).exists())

    def test_webhook_invalid_signature_returns_401_and_creates_nothing(self):
        body = json.dumps(
            {
                "event": "charge.success",
                "data": {"reference": self.tx.reference},
            },
            separators=(",", ":"),
        ).encode()
        # Wrong signature
        sig = "deadbeef"
        resp = self.client.post(
            reverse("orders:paystack_webhook"),
            body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig,
        )
        self.assertEqual(resp.status_code, 401)
        self.assertIn("invalid signature", resp.content.decode())
        self.assertFalse(PaymentEvent.objects.exists())

    def test_webhook_replay_same_body_returns_200_without_duplicate_transaction(self):
        body = json.dumps(
            {
                "event": "charge.success",
                "data": {"reference": self.tx.reference, "metadata": {"order_id": self.order.id}},
            },
            separators=(",", ":"),
        ).encode()
        sig = self._sign(body)
        url = reverse("orders:paystack_webhook")
        r1 = self.client.post(
            url, body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig
        )
        r2 = self.client.post(
            url, body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=sig
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(PaymentEvent.objects.count(), 1)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, "success")
        # body_sha256 set on the transaction for idempotency
        import hashlib as _hashlib

        expected_sha = _hashlib.sha256(body).hexdigest().lower()
        self.assertEqual(self.tx.body_sha256, expected_sha)

    def test_webhook_malformed_json_returns_400(self):
        # Intentionally malformed JSON (missing closing brace)
        bad = b'{"event":"charge.success","data":{"reference":"%s"}' % self.tx.reference.encode()
        sig = self._sign(bad)
        resp = self.client.post(
            reverse("orders:paystack_webhook"),
            bad,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("invalid json", resp.content.decode())
        self.assertEqual(PaymentEvent.objects.count(), 0)

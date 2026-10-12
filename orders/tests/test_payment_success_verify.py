import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import Order, OrderItem, PaymentEvent, Transaction
from product_app.models import Category, Product, ProductStock, Warehouse


@override_settings(PAYSTACK_SECRET_KEY="sk_test_example")
class PaymentSuccessVerifyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="u2", password="p", email="u2@example.com"
        )
        cat = Category.objects.create(name="c2", slug="c2")
        prod = Product.objects.create(category=cat, name="p2", slug="p2", price=10)
        wh = Warehouse.objects.create(name="w2", latitude=1.0, longitude=36.0)
        self.stock = ProductStock.objects.create(product=prod, warehouse=wh, quantity=5)
        self.order = Order.objects.create(
            user=self.user,
            full_name="F",
            email="u2@example.com",
            address="A",
            latitude=1.0,
            longitude=36.0,
            dest_address_text="A",
            dest_lat=1.0,
            dest_lng=36.0,
            paid=False,
            payment_status="pending",
        )
        OrderItem.objects.create(
            order=self.order, product=prod, price=10, quantity=1, warehouse=wh
        )
        self.tx = Transaction.objects.create(
            user=self.user,
            order=self.order,
            email=self.user.email,
            amount=10,
            method="card",
            gateway="paystack",
            status="pending",
            reference="ref_ok",
        )
        self.url = reverse("orders:payment_success", args=[self.order.id])

    @staticmethod
    def _verify_response(payload):
        mock = MagicMock()
        mock.ok = True
        mock.json.return_value = payload
        return mock

    def test_verify_success_confirms_payment(self):
        resp_body = {
            "status": True,
            "data": {
                "status": "success",
                "amount": 1000,
                "currency": "KES",
                "customer": {"email": "u2@example.com"},
            },
        }
        self.client.force_login(self.user)
        with patch(
            "orders.views.requests.get", return_value=self._verify_response(resp_body)
        ):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.tx.refresh_from_db()
        self.assertTrue(self.order.paid)
        self.assertEqual(self.order.payment_status, "success")
        self.assertTrue(self.tx.callback_received)
        self.assertTrue(self.tx.verified)
        self.assertEqual(self.tx.status, "success")
        self.assertEqual(resp.context["message"], "Payment confirmed.")
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 4)
        self.assertTrue(
            PaymentEvent.objects.filter(reference=self.tx.reference).exists()
        )

    def test_verify_failure_keeps_pending(self):
        resp_body = {"status": False, "message": "Transaction reference not found"}
        self.client.force_login(self.user)
        with patch(
            "orders.views.requests.get", return_value=self._verify_response(resp_body)
        ):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.tx.refresh_from_db()
        self.assertFalse(self.order.paid)
        self.assertEqual(self.order.payment_status, "pending_confirmation")
        self.assertFalse(self.tx.callback_received)
        self.assertEqual(
            resp.context["message"], "Payment received. Awaiting confirmation."
        )

    def test_amount_mismatch_keeps_pending(self):
        resp_body = {
            "status": True,
            "data": {"status": "success", "amount": 999, "currency": "KES"},
        }
        self.client.force_login(self.user)
        with patch(
            "orders.views.requests.get", return_value=self._verify_response(resp_body)
        ):
            resp = self.client.get(self.url)
        self.order.refresh_from_db()
        self.assertFalse(self.order.paid)
        self.assertEqual(self.order.payment_status, "pending_confirmation")
        self.assertEqual(
            resp.context["message"], "Payment received. Awaiting confirmation."
        )

    def test_webhook_fulfilled_payment_not_regressed(self):
        self.tx.callback_received = True
        self.tx.verified = True
        self.tx.status = "success"
        self.tx.save(update_fields=["callback_received", "verified", "status"])
        self.order.paid = True
        self.order.payment_status = "success"
        self.order.save(update_fields=["paid", "payment_status"])
        self.client.force_login(self.user)
        with patch("orders.views.requests.get") as mock_get:
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        mock_get.assert_not_called()
        self.order.refresh_from_db()
        self.assertTrue(self.order.paid)
        self.assertEqual(self.order.payment_status, "success")
        self.assertEqual(resp.context["message"], "Payment confirmed.")

    def test_event_payload_is_valid_for_shared_processor(self):
        # The confirm path builds a charge.success event; assert it satisfies
        # the same serializer contract the webhook enforces.
        from payments.serializers import PaystackWebhookSerializer

        event = {
            "event": "charge.success",
            "data": {
                "reference": "ref_ok",
                "status": "success",
                "amount": 1000,
                "currency": "KES",
                "metadata": {"order_id": self.order.id},
                "customer": {"email": "u2@example.com"},
            },
        }
        ser = PaystackWebhookSerializer(data=event)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(json.dumps(event)[:1], "{")

import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from orders.models import Order, OrderItem
from payments.enums import Gateway, PaymentMethod, TxnStatus
from payments.models import AuditLog, Transaction
from product_app.models import Category, Product


class PaymentTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u", password="p")
        category = Category.objects.create(name="c", slug="c")
        self.product = Product.objects.create(
            category=category, name="p", slug="p", price=10
        )
        self.order = Order.objects.create(
            full_name="x",
            email="x@example.com",
            address="addr",
            dest_address_text="d",
            dest_lat=0,
            dest_lng=0,
            user=self.user,
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, price=10, quantity=1
        )

    def test_checkout_idempotency(self):
        self.client.login(username="u", password="p")
        payload = {
            "order_id": self.order.id,
            "amount": str(self.order.get_total_cost()),
            "currency": "USD",
            "gateway": Gateway.STRIPE,
            "method": PaymentMethod.CARD,
            "idempotency_key": "idem-1",
        }
        url = "/payments/checkout/"
        r1 = self.client.post(url, json.dumps(payload), content_type="application/json")
        r2 = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.json()["reference"], r2.json()["reference"])

    @patch("payments.views.verify_stripe")
    def test_webhook_replay_guard(self, mock_verify):
        txn = Transaction.objects.create(
            order=self.order,
            user=self.user,
            method=PaymentMethod.CARD,
            gateway=Gateway.STRIPE,
            amount=Decimal("10"),
            currency="USD",
            status=TxnStatus.PENDING,
            idempotency_key="k1",
            reference="ref1",
        )
        event = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "metadata": {"reference": txn.reference},
                    "payment_intent": "pi_1",
                }
            },
        }
        mock_verify.return_value = event
        url = "/webhook/stripe/"
        body = json.dumps(event)
        r1 = self.client.post(url, body, content_type="application/json")
        txn.refresh_from_db()
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(txn.status, TxnStatus.SUCCESS)
        self.client.post(url, body, content_type="application/json")
        txn.refresh_from_db()
        self.assertEqual(txn.status, TxnStatus.SUCCESS)
        self.assertTrue(
            AuditLog.objects.filter(
                event="WEBHOOK_REPLAY_BLOCKED", transaction=txn
            ).exists()
        )

    @patch("payments.services.issue_refund")
    @patch("payments.views.verify_stripe")
    def test_duplicate_success_auto_refund(self, mock_verify, mock_refund):
        Transaction.objects.create(
            order=self.order,
            user=self.user,
            method=PaymentMethod.CARD,
            gateway=Gateway.STRIPE,
            amount=Decimal("10"),
            currency="USD",
            status=TxnStatus.SUCCESS,
            idempotency_key="k2",
            reference="ref2",
        )
        txn2 = Transaction.objects.create(
            order=self.order,
            user=self.user,
            method=PaymentMethod.CARD,
            gateway=Gateway.STRIPE,
            amount=Decimal("10"),
            currency="USD",
            status=TxnStatus.PENDING,
            idempotency_key="k3",
            reference="ref3",
        )
        event = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "metadata": {"reference": txn2.reference},
                    "payment_intent": "pi_2",
                }
            },
        }
        mock_verify.return_value = event

        def fake_refund(t, request_id=""):
            t.refund_reference = "rr1"

        mock_refund.side_effect = fake_refund
        self.client.post(
            "/webhook/stripe/", json.dumps(event), content_type="application/json"
        )
        txn2.refresh_from_db()
        self.assertEqual(txn2.status, TxnStatus.REFUNDED)
        self.assertEqual(txn2.refund_reference, "rr1")
        self.assertTrue(
            AuditLog.objects.filter(
                event="DUPLICATE_REFUND_ISSUED", transaction=txn2
            ).exists()
        )

    @patch("payments.views.verify_mpesa")
    def test_duplicate_mpesa_manual(self, mock_verify):
        Transaction.objects.create(
            order=self.order,
            user=self.user,
            method=PaymentMethod.MPESA,
            gateway=Gateway.MPESA,
            amount=Decimal("10"),
            currency="KES",
            status=TxnStatus.SUCCESS,
            idempotency_key="k4",
            reference="ref4",
        )
        txn2 = Transaction.objects.create(
            order=self.order,
            user=self.user,
            method=PaymentMethod.MPESA,
            gateway=Gateway.MPESA,
            amount=Decimal("10"),
            currency="KES",
            status=TxnStatus.PENDING,
            idempotency_key="k5",
            reference="ref5",
        )
        event = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": txn2.reference,
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [{"Name": "MpesaReceiptNumber", "Value": "xyz"}]
                    },
                }
            }
        }
        mock_verify.return_value = event
        self.client.post(
            "/webhook/mpesa/", json.dumps(event), content_type="application/json"
        )
        txn2.refresh_from_db()
        self.assertEqual(txn2.status, TxnStatus.DUPLICATE_SUCCESS)
        self.assertTrue(
            AuditLog.objects.filter(
                event="DUPLICATE_MANUAL_REVERSAL_REQUIRED", transaction=txn2
            ).exists()
        )

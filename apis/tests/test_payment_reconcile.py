import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from orders.models import Order, OrderItem
from payments.enums import Gateway, PaymentMethod, TxnStatus
from payments.models import Transaction
from payments.services.reconcile import VerifyResult
from product_app.models import Category, Product, ProductStock, Warehouse


@override_settings(PAYSTACK_SECRET_KEY="sk_test")
class PaymentReconcileAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass1234"
        )
        self.client.force_login(self.admin)

        self.category = Category.objects.create(name="Shirts", slug="shirts")
        self.product = Product.objects.create(
            category=self.category,
            name="Tee",
            slug="tee",
            price=Decimal("100"),
            owner=self.admin,
        )
        self.warehouse = Warehouse.objects.create(
            name="Main",
            latitude=1.0,
            longitude=36.0,
            address="HQ",
        )
        self.stock = ProductStock.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            quantity=5,
        )
        self.order = Order.objects.create(
            user=self.admin,
            full_name="Rahim",
            email="rahim@example.com",
            address="Nairobi",
            dest_address_text="Nairobi",
            dest_lat=0,
            dest_lng=0,
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            price=Decimal("100"),
            quantity=1,
            warehouse=self.warehouse,
        )
        self.txn = Transaction.objects.create(
            order=self.order,
            user=self.admin,
            method=PaymentMethod.CARD,
            gateway=Gateway.PAYSTACK,
            amount=Decimal("100"),
            currency="KES",
            status=TxnStatus.PENDING,
            idempotency_key="idem-1",
            reference="ref-123",
        )

    @patch("payments.services.reconcile._fetch_paystack_status")
    def test_paystack_success_idempotent(self, mock_fetch):
        mock_fetch.return_value = VerifyResult(
            status="success",
            reference="paystack-ref",
            raw={"data": {"status": "success"}},
        )
        payload = {"gateway": Gateway.PAYSTACK, "ref": self.txn.reference}

        r1 = self.client.post(
            "/apis/v1/payments/reconcile/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(r1.status_code, 200)
        body1 = r1.json()
        self.assertTrue(body1["ok"])
        self.assertFalse(body1["cached"])
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 4)
        self.order.refresh_from_db()
        self.assertTrue(self.order.paid)
        self.assertTrue(self.order.stock_updated)
        self.assertEqual(self.order.payment_status.lower(), "paid")
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TxnStatus.SUCCESS)

        r2 = self.client.post(
            "/apis/v1/payments/reconcile/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(r2.status_code, 200)
        body2 = r2.json()
        self.assertTrue(body2["cached"])
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 4)
        self.assertEqual(mock_fetch.call_count, 2)

    @patch("payments.services.reconcile._fetch_paystack_status")
    def test_paystack_failure_returns_conflict(self, mock_fetch):
        mock_fetch.return_value = VerifyResult(
            status="failed",
            reference="paystack-ref",
            raw={"data": {"status": "failed"}},
        )
        payload = {"gateway": Gateway.PAYSTACK, "ref": self.txn.reference}

        resp = self.client.post(
            "/apis/v1/payments/reconcile/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body.get("code"), "gateway_failed")
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)
        self.order.refresh_from_db()
        self.assertFalse(self.order.paid)
        self.assertFalse(self.order.stock_updated)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.status, TxnStatus.FAILED)

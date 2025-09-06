import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from product_app.models import Category, Product
from orders.models import Order, OrderItem
from payments.models import Transaction
from payments.enums import Gateway, PaymentMethod, TxnStatus


@override_settings(PAYSTACK_SECRET_KEY="secret")
class PaystackWebhookSigTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u", password="p")
        category = Category.objects.create(name="c", slug="c")
        self.product = Product.objects.create(category=category, name="p", slug="p", price=10)
        self.order = Order.objects.create(
            full_name="x",
            email="x@example.com",
            address="addr",
            dest_address_text="d",
            dest_lat=0,
            dest_lng=0,
            user=self.user,
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=10, quantity=1)
        self.txn = Transaction.objects.create(
            order=self.order,
            user=self.user,
            method=PaymentMethod.CARD,
            gateway=Gateway.PAYSTACK,
            amount=Decimal("10"),
            currency="KES",
            status=TxnStatus.PENDING,
            idempotency_key="idem-x",
            reference="ref-x",
        )

    def test_invalid_signature_returns_400(self):
        event = {"data": {"reference": self.txn.reference, "status": "success"}}
        body = json.dumps(event)
        resp = self.client.post("/webhook/paystack/", body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE="bad")
        self.assertEqual(resp.status_code, 400)


import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import Order, OrderItem, PaymentEvent, Transaction
from product_app.models import Category, Product, ProductStock, Warehouse


@override_settings(PAYSTACK_SECRET_KEY="secret")
class PaystackWebhookTests(TestCase):
    @patch("orders.views.assign_warehouses_and_update_stock")
    def test_charge_success_updates_records(self, mock_assign):
        User = get_user_model()
        user = User.objects.create_user(username="u", password="p", email="u@example.com")
        cat = Category.objects.create(name="c", slug="c")
        prod = Product.objects.create(category=cat, name="p", slug="p", price=10)
        wh = Warehouse.objects.create(name="w", latitude=1.0, longitude=36.0)
        ProductStock.objects.create(product=prod, warehouse=wh, quantity=5)
        order = Order.objects.create(
            user=user,
            full_name="F",
            email="e@e.com",
            address="A",
            latitude=1.0,
            longitude=36.0,
            dest_address_text="A",
            dest_lat=1.0,
            dest_lng=36.0,
        )
        OrderItem.objects.create(order=order, product=prod, price=10, quantity=1, warehouse=wh)
        tx = Transaction.objects.create(
            user=user,
            order=order,
            email=user.email,
            amount=10,
            method="card",
            gateway="paystack",
            status="pending",
            reference="ref123",
        )
        body = json.dumps(
            {
                "event": "charge.success",
                "data": {
                    "reference": tx.reference,
                    "metadata": {"order_id": order.id},
                    "customer": {"email": user.email},
                },
            }
        ).encode()
        sig = hmac.new(b"secret", body, hashlib.sha512).hexdigest()
        resp = self.client.post(
            reverse("orders:paystack_webhook"),
            body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=sig,
        )
        self.assertEqual(resp.status_code, 200)
        tx.refresh_from_db()
        order.refresh_from_db()
        self.assertTrue(tx.callback_received)
        self.assertTrue(tx.verified)
        self.assertEqual(tx.status, "success")
        self.assertTrue(order.paid)
        self.assertEqual(order.payment_status, "success")
        self.assertTrue(PaymentEvent.objects.filter(reference=tx.reference).exists())
        mock_assign.assert_called_once_with(order)

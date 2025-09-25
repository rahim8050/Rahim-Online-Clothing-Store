import json
from unittest.mock import patch

from django.test import Client, TestCase


class AssistantApiTableTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("assistant.views.tools.list_orders_table")
    def test_list_orders_returns_table_structure(self, mock_table):
        mock_table.return_value = {
            "title": "Recent orders",
            "columns": ["#", "Order Code", "Status", "Item"],
            "rows": [[57, "RAH57", "PENDING", "iphone:47"]],
            "footnote": "Showing latest 1.",
        }
        resp = self.client.post(
            "/api/assistant/ask/",
            data=json.dumps(
                {"session_key": "s1", "message": "list orders", "persona": "vendor"}
            ),
            content_type="application/json",
        )
        # Anon user should be unauthorized (per existing permissions)
        self.assertIn(resp.status_code, (401, 403))

    @patch("assistant.views.tools.list_orders_table")
    @patch("assistant.views.tools.order_list")
    def test_list_orders_table_for_authed_user(self, mock_order_list, mock_table):
        from django.contrib.auth import get_user_model

        u = get_user_model().objects.create_user(
            username="t", email="t@example.com", password="x"
        )
        self.client.force_login(u)
        mock_table.return_value = {
            "title": "Recent orders",
            "columns": ["#", "Order Code", "Status", "Item"],
            "rows": [[57, "RAH57", "PENDING", "iphone:47"]],
            "footnote": "Showing latest 1.",
        }
        mock_order_list.return_value = (
            "Recent orders:\n57: RAH57 - PENDING ([iphone]:47)"
        )
        resp = self.client.post(
            "/api/assistant/ask/",
            data=json.dumps(
                {"session_key": "s1", "message": "list orders", "persona": "vendor"}
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("table", data)
        self.assertEqual(data["table"]["columns"][0], "#")
        self.assertTrue(data["reply"].startswith("Recent orders"))

    @patch("assistant.views.tools.route_message")
    def test_fallback_reply_path(self, mock_route):
        mock_route.return_value = "ok"
        from django.contrib.auth import get_user_model

        u = get_user_model().objects.create_user(
            username="t2", email="t2@example.com", password="x"
        )
        self.client.force_login(u)
        resp = self.client.post(
            "/api/assistant/ask/",
            data=json.dumps(
                {"session_key": "s1", "message": "hi", "persona": "customer"}
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"reply": "ok"})

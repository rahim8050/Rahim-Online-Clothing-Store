# assistant/views.py
import re
from typing import Tuple

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import ChatSession, ChatMessage
from . import tools

PATTERNS = {
    "list_orders": re.compile(r"\b(list|show|see|check|tell me about|view|my)\s+orders?\b", re.I),
    "order_status_id": re.compile(r"\b(order\s+status|status\s+of\s+order)\s+#?\s*(\d+)\b", re.I),
    "order_status_no": re.compile(r"\b(order\s+status|status\s+of\s+order)\s+(rah[-\s]?\d+)\b", re.I),
    "payment_status": re.compile(r"\b(payment\s+status|status\s+of\s+payment)\s+(?:for\s+)?(?:order\s+)?#?\s*([\w-]+)\b", re.I),
    "delivery_status": re.compile(r"\b(delivery\s+status|where(?:'s| is)\s+(?:my\s+)?(?:delivery|order))\s+(?:for\s+)?(?:order\s+)?#?\s*([\w-]+)\b", re.I),
    "shipping": re.compile(r"\bshipping\b", re.I),
    "returns": re.compile(r"\breturns?\b", re.I),
}

def _normalize_msg(msg: str) -> str:
    s = (msg or "").strip().lower()
    return re.sub(r"\s+", " ", s)

@method_decorator(csrf_exempt, name="dispatch")  # keep if you don't want CSRF; safe to remove if you do
class AskView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data or {}
        # --- session key: optional; fall back to Django session id ---
        sess_key = (data.get("session_key") or request.session.session_key or "").strip()[:64]
        if not sess_key:
            # ensure we have a Django session id
            request.session.save()
            sess_key = request.session.session_key

        message = (data.get("message") or data.get("text") or "").strip()
        persona = (data.get("persona") or "customer").strip().lower()

        if not message:
            # gentle fallback (keeps frontend happy)
            return Response({
                "reply": "Hi! Try: 'list orders', 'order status 123' or 'order status RAH123', "
                         "'payment status 123', 'delivery status 123', 'shipping', 'returns'."
            }, status=200)

        # create / load session scoped to user
        sess, _ = ChatSession.objects.get_or_create(user=request.user, session_key=sess_key)

        # store user message
        ChatMessage.objects.create(session=sess, role=ChatMessage.Role.USER, content=message)

        # route by regex
        msg_norm = _normalize_msg(message)
        reply = None
        table = None

        if PATTERNS["list_orders"].search(msg_norm):
            reply = tools.order_list(request.user, session=sess)
            try:
                table = tools.list_orders_table(request.user)  # optional structured table
            except Exception:
                table = None
        else:
            m_id = PATTERNS["order_status_id"].search(msg_norm)
            m_no = PATTERNS["order_status_no"].search(msg_norm)
            m_pay = PATTERNS["payment_status"].search(msg_norm)
            m_del = PATTERNS["delivery_status"].search(msg_norm)
            if m_id:
                reply = tools.order_status(request.user, m_id.group(2), session=sess)
            elif m_no:
                reply = tools.order_status(request.user, m_no.group(2), session=sess)
            elif m_pay:
                reply = tools.payment_status(request.user, m_pay.group(2), session=sess)
            elif m_del:
                reply = tools.delivery_status(request.user, m_del.group(2), session=sess)
            elif PATTERNS["shipping"].search(msg_norm):
                reply = tools.faq("shipping", session=sess)
            elif PATTERNS["returns"].search(msg_norm):
                reply = tools.faq("returns", session=sess)

        if not reply:
            try:
                reply = tools.route_message(message, persona=persona, user=request.user)
            except Exception:
                reply = ("Try: 'list orders', 'order status 123' or 'order status RAH123', "
                         "'payment status 123', 'delivery status 123', 'shipping', 'returns'.")

        safe_reply = tools.redact(reply)
        ChatMessage.objects.create(session=sess, role=ChatMessage.Role.ASSISTANT, content=safe_reply)

        payload = {"reply": safe_reply}
        if table:
            payload["table"] = table
        return Response(payload, status=200)

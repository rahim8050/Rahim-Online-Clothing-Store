import re
from typing import Tuple

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ChatSession, ChatMessage
from . import tools


PATTERNS = {
    "list_orders": re.compile(r"\b(list|show|see|check|tell me about|view|my)\s+orders?\b", re.I),
    "order_status_id": re.compile(r"\b(order\s+status|status\s+of\s+order)\s+#?\s*(\d+)\b", re.I),
    "order_status_no": re.compile(r"\b(order\s+status|status\s+of\s+order)\s+(rah[-\s]?\d+)\b", re.I),
    "payment_status": re.compile(r"\b(payment\s+status|status\s+of\s+payment)\s+(?:for\s+)?(?:order\s+)?#?\s*([\w-]+)\b", re.I),
    "delivery_status": re.compile(r"\b(delivery\s+status|where('?| i)?s\s+my\s+delivery|where('?| i)?s\s+my\s+order)\s+(?:for\s+)?(?:order\s+)?#?\s*([\w-]+)\b", re.I),
    "shipping": re.compile(r"\bshipping\b", re.I),
    "returns": re.compile(r"\breturns?\b", re.I),
}


def _normalize_msg(msg: str) -> str:
    s = (msg or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


class AskView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data or {}
        session_key = (data.get("session_key") or "").strip()[:64]
        message = (data.get("message") or "").strip()

        if not session_key:
            return Response({"detail": "session_key required"}, status=400)
        if not message:
            return Response({"detail": "message required"}, status=400)

        # Create / load session scoped to user
        sess, _ = ChatSession.objects.get_or_create(user=request.user, session_key=session_key)

        # Store user message
        ChatMessage.objects.create(session=sess, role=ChatMessage.Role.USER, content=message)

        # Route by regex
        msg_norm = _normalize_msg(message)
        reply = None

        if PATTERNS["list_orders"].search(msg_norm):
            reply = tools.order_list(request.user, session=sess)
        else:
            m_id = PATTERNS["order_status_id"].search(msg_norm)
            m_no = PATTERNS["order_status_no"].search(msg_norm)
            m_pay = PATTERNS["payment_status"].search(msg_norm)
            m_del = PATTERNS["delivery_status"].search(msg_norm)
            if m_id:
                token = m_id.group(2)
                reply = tools.order_status(request.user, token, session=sess)
            elif m_no:
                token = m_no.group(2)
                reply = tools.order_status(request.user, token, session=sess)
            elif m_pay:
                token = m_pay.group(2)
                reply = tools.payment_status(request.user, token, session=sess)
            elif m_del:
                token = m_del.group(2)
                reply = tools.delivery_status(request.user, token, session=sess)
            elif PATTERNS["shipping"].search(msg_norm):
                reply = tools.faq("shipping", session=sess)
            elif PATTERNS["returns"].search(msg_norm):
                reply = tools.faq("returns", session=sess)

        if not reply:
            reply = (
                "Try: 'list orders', 'order status 123' or 'order status RAH123', "
                "'payment status 123', 'delivery status 123', 'shipping', 'returns'."
            )

        # Redact reply for privacy
        safe_reply = tools.redact(reply)

        ChatMessage.objects.create(session=sess, role=ChatMessage.Role.ASSISTANT, content=safe_reply)
        return Response({"reply": safe_reply})


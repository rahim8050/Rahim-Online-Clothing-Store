import re
from dataclasses import asdict, is_dataclass
from typing import Any

from django.apps import apps
from django.utils import timezone

from orders.models import Order, OrderItem
from orders.utils import derive_ui_payment_status

from .models import ChatSession, ToolCallLog
import logging

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.I)
PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b")


def redact(text: str) -> str:
    if not isinstance(text, str):
        return text
    t = EMAIL_RE.sub("[email]", text)
    t = PHONE_RE.sub("[phone]", t)
    return t


def _fmt_dt(dt) -> str:
    if not dt:
        return "-"
    try:
        return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)


def _normalize_order_token(token: str | int) -> int | None:
    try:
        return int(token)
    except Exception as e:
        logger.debug("Non-fatal parse/log failure: %s", e, exc_info=True)
    if not token:
        return None
    s = str(token).strip().upper()
    s = re.sub(r"\s+", "", s)
    s = s.replace("RAH-", "RAH")
    m = re.match(r"RAH(\d+)$", s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    # Last resort: digits inside
    digits = re.sub(r"\D+", "", s)
    return int(digits) if digits.isdigit() else None


def _get_order(user, token):
    Order = apps.get_model("orders", "Order")
    order_id = _normalize_order_token(token)
    if not order_id:
        return None
    try:
        o = Order.objects.select_related("user").get(pk=order_id, user=user)
        return o
    except Order.DoesNotExist:
        return None


def _redact_args(v: Any) -> Any:
    if isinstance(v, str):
        return redact(v)
    if isinstance(v, dict):
        return {k: _redact_args(val) for k, val in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_redact_args(x) for x in v]
    if is_dataclass(v):
        return _redact_args(asdict(v))
    return v


def _log(session: ChatSession | None, name: str, args: dict) -> None:
    if not session:
        return
    try:
        ToolCallLog.objects.create(
            session=session,
            tool_name=name,
            args=_redact_args(args or {}),
        )
    except Exception as e:
        # logging must never fail the chat
        logger.debug("Non-fatal parse/log failure: %s", e, exc_info=True)


def _order_number(o) -> str:
    return f"RAH{o.id}"


def order_list(user, limit: int = 5, session: ChatSession | None = None) -> str:
    _log(session, "order_list", {"limit": limit})
    Order = apps.get_model("orders", "Order")
    qs = Order.objects.filter(user=user).order_by("-created_at")[
        : max(1, min(20, int(limit)))
    ]
    if not qs:
        return "You have no recent orders."
    lines = ["Recent orders:"]
    for o in qs:
        last_tx = None
        status = derive_ui_payment_status(o, last_tx)
        lines.append(f"{o.id}: {_order_number(o)} — {status} ({_fmt_dt(o.created_at)})")
    return redact("\n".join(lines))


def list_orders_table(user, limit: int = 10) -> dict:
    """Structured table for recent orders used by the new ChatPanel.
    Columns: [#, Order Code, Status, Item]
    """
    qs = (
        Order.objects.filter(user=user)
        .order_by("-created_at")
        .only("id", "paid", "payment_status")[: max(1, min(50, int(limit)))]
    )
    ids = [o.id for o in qs]
    first_items = {
        it["order_id"]: it
        for it in (
            OrderItem.objects.filter(order_id__in=ids)
            .select_related("product")
            .values("order_id", "product__name", "quantity")
            .order_by("order_id", "id")
        )
    }
    rows = []
    for o in qs:
        item = first_items.get(o.id)
        item_str = f"{item['product__name']}:{item['quantity']}" if item else "-"
        status = derive_ui_payment_status(o)
        rows.append([o.id, f"RAH{o.id}", status, item_str])
    return {
        "title": "Recent orders",
        "columns": ["#", "Order Code", "Status", "Item"],
        "rows": rows,
        "footnote": f"Showing latest {len(rows)}.",
    }


# Minimal routing fallback for tests/new UI
def route_message(msg: str, persona: str = "customer", user=None) -> str:
    msg = (msg or "").strip().lower()
    if msg.startswith("list orders"):
        return order_list(user)
    return "Try 'list orders', 'order status 123', 'payment status 123', 'delivery status 123'."


def order_status(user, token: str, session: ChatSession | None = None) -> str:
    _log(session, "order_status", {"token": token})
    o = _get_order(user, token)
    if not o:
        return "Sorry, I couldn't find that order for your account."
    total = getattr(o, "get_total_cost", None)
    total_val = total() if callable(total) else "-"
    status = derive_ui_payment_status(o)
    return redact(
        f"Order {_order_number(o)}: status={status}, total={total_val}, placed={_fmt_dt(o.created_at)}."
    )


def payment_status(user, token: str, session: ChatSession | None = None) -> str:
    _log(session, "payment_status", {"token": token})
    o = _get_order(user, token)
    if not o:
        return "Sorry, I couldn't find that order for your account."
    Transaction = apps.get_model("orders", "Transaction")
    tx = Transaction.objects.filter(order=o).order_by("-created_at").first()
    if not tx:
        status = derive_ui_payment_status(o)
        return redact(
            f"Order {_order_number(o)}: payment status={status}. No gateway events yet."
        )
    return redact(
        f"Order {_order_number(o)}: payment via {tx.gateway} is {tx.status} ({_fmt_dt(tx.created_at)})."
    )


def delivery_status(user, token: str, session: ChatSession | None = None) -> str:
    _log(session, "delivery_status", {"token": token})
    o = _get_order(user, token)
    if not o:
        return "Sorry, I couldn't find that order for your account."
    Delivery = apps.get_model("orders", "Delivery")
    d = Delivery.objects.filter(order=o).order_by("-id").first()
    if not d:
        return redact(f"Order {_order_number(o)}: no delivery has been assigned yet.")
    last = _fmt_dt(d.last_ping_at)
    return redact(
        f"Order {_order_number(o)}: delivery status={d.status}, last update={last}."
    )


FAQS = {
    "shipping": (
        "Shipping: We deliver Mon–Sat, 9am–6pm. Nairobi deliveries typically arrive same or next day after confirmation."
    ),
    "returns": (
        "Returns: 7‑day return window for unused items with tags. Start a return from your orders page or contact support."
    ),
}


def faq(key: str, session: ChatSession | None = None) -> str:
    _log(session, "faq", {"key": key})
    return redact(FAQS.get(key, "I can help with shipping and returns."))

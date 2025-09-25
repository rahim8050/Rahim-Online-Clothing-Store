from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from payments.models import Refund, Transaction

from .models import VendorKPI


def _period_bounds(d: date, window: str) -> tuple[date, date]:
    if window == VendorKPI.Window.DAILY:
        return d, d
    if window == VendorKPI.Window.WEEKLY:
        start = d - timedelta(days=d.weekday())
        end = start + timedelta(days=6)
        return start, end
    if window == VendorKPI.Window.MONTHLY:
        start = d.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1) - timedelta(days=1)
        return start, end
    return d, d


def aggregate_kpis_daily(org_id: int, for_date: date | None = None) -> VendorKPI:
    """Compute and store daily KPIs for a VendorOrg from transactions/refunds."""
    d = for_date or timezone.now().date()
    start, end = _period_bounds(d, VendorKPI.Window.DAILY)

    # Transactions scoped to org and date
    tx_qs = Transaction.objects.filter(
        vendor_org_id=org_id, processed_at__date__gte=start, processed_at__date__lte=end
    )
    gross = tx_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    success = tx_qs.filter(status="success").count()
    total = tx_qs.count()
    success_rate = (
        Decimal("0.00") if total == 0 else (Decimal(success) * 100 / Decimal(total))
    )

    # Net revenue available on Transaction
    net = tx_qs.aggregate(s=Sum("net_to_vendor"))["s"] or Decimal("0.00")

    # Refunds
    refunds = Refund.objects.filter(
        transaction__vendor_org_id=org_id,
        status=Refund.Status.SUCCEEDED,
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()

    kpi, _ = VendorKPI.objects.update_or_create(
        org_id=org_id,
        window=VendorKPI.Window.DAILY,
        period_start=start,
        defaults={
            "period_end": end,
            "gross_revenue": gross,
            "net_revenue": net,
            "orders": success,
            "refunds": refunds,
            "success_rate": success_rate,
            # fulfillment averaging hook stub (set to 0 for now)
            "fulfillment_avg_mins": Decimal("0.00"),
        },
    )
    return kpi


# --------- Realtime snapshot using cache ---------


def _rt_key(org_id: int) -> str:
    return f"kpi:rt:org:{org_id}"


def bump_realtime_on_success(org_id: int, amount: Decimal, net: Decimal):
    key = _rt_key(org_id)
    snap = cache.get(key) or {
        "gross_revenue": Decimal("0.00"),
        "net_revenue": Decimal("0.00"),
        "orders": 0,
    }
    snap["gross_revenue"] = Decimal(snap["gross_revenue"]) + Decimal(amount)
    snap["net_revenue"] = Decimal(snap["net_revenue"]) + Decimal(net)
    snap["orders"] = int(snap["orders"]) + 1
    cache.set(key, snap, timeout=3600)


def bump_realtime_on_refund(org_id: int):
    key = _rt_key(org_id)
    snap = cache.get(key) or {
        "gross_revenue": Decimal("0.00"),
        "net_revenue": Decimal("0.00"),
        "orders": 0,
        "refunds": 0,
    }
    snap["refunds"] = int(snap.get("refunds", 0)) + 1
    cache.set(key, snap, timeout=3600)


def get_realtime_kpi_snapshot(org_id: int):
    return cache.get(_rt_key(org_id)) or {
        "gross_revenue": "0.00",
        "net_revenue": "0.00",
        "orders": 0,
        "refunds": 0,
    }

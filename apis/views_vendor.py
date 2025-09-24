from __future__ import annotations

from datetime import timedelta

from django.apps import apps
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils.timezone import now
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from product_app.utils import get_vendor_field
from users.permissions import IsVendorOrVendorStaff
from users.utils import resolve_vendor_owner_for


# --------- Doc helper serializers (module-level) ---------
class VendorKPIsProductsSerializer(serializers.Serializer):  # guessed; refine as needed
    total = serializers.IntegerField()
    live = serializers.IntegerField()


class VendorKPIsSeriesEntrySerializer(serializers.Serializer):  # guessed; refine as needed
    date = serializers.DateField()
    orders = serializers.IntegerField()
    revenue = serializers.FloatField()


class VendorKPIsLastPayoutSerializer(serializers.Serializer):  # guessed; refine as needed
    amount = serializers.FloatField()
    created_at = serializers.DateTimeField()


class VendorKPIsResponseSerializer(serializers.Serializer):  # guessed; refine as needed
    products = VendorKPIsProductsSerializer()
    orders_30d = serializers.IntegerField()
    revenue_30d = serializers.FloatField()
    series_14d = VendorKPIsSeriesEntrySerializer(many=True)
    last_payout = VendorKPIsLastPayoutSerializer(allow_null=True)


class VendorKPIAPI(APIView):
    """GET /apis/vendor/kpis/?owner_id=<id>
    Returns vendor KPIs for dashboard: products totals, last 30d orders & revenue,
    and a 14-day series of daily orders and revenue.
    """

    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff]
    # no request body on GET
    serializer_class = VendorKPIsResponseSerializer

    @extend_schema(request=None, responses=VendorKPIsResponseSerializer)
    def get(self, request):
        Product = apps.get_model("product_app", "Product")
        Order = apps.get_model("orders", "Order")
        Transaction = apps.get_model("orders", "Transaction")

        try:
            owner_id = resolve_vendor_owner_for(request.user, request.query_params.get("owner_id"))
        except ValueError as e:
            return Response({"owner_id": str(e)}, status=400)

        today = now().date()
        since_30 = now() - timedelta(days=30)
        since_14 = now() - timedelta(days=14)

        # Products totals
        field = get_vendor_field(Product)
        vendor_filter = {f"{field}_id": owner_id}
        total_products = Product.objects.filter(**vendor_filter).count()
        live_products = Product.objects.filter(**vendor_filter, available=True).count()

        # Orders in last 30 days: distinct orders that include at least one vendor product
        vendor_item_q = Q(**{f"items__product__{field}_id": owner_id})
        orders_30_qs = Order.objects.filter(vendor_item_q, created_at__gte=since_30).distinct()
        orders_30d = orders_30_qs.count()

        # Revenue in last 30 days: sum successful transactions for those orders
        rev_map = {
            t["order_id"]: t["amount"]
            for t in (
                Transaction.objects.filter(
                    order__in=orders_30_qs, status="success", created_at__gte=since_30
                )
                .values("order_id")
                .annotate(amount=Sum("amount"))
            )
        }
        revenue_30d = float(sum(rev_map.values())) if rev_map else 0.0

        # 14d series by order created date
        series_orders = (
            orders_30_qs.filter(created_at__gte=since_14)
            .annotate(d=TruncDate("created_at"))
            .values("d")
            .annotate(n=Count("id", distinct=True))
        )
        orders_by_day = {str(r["d"]): int(r["n"]) for r in series_orders}

        # Revenue by day over same period
        tx_14 = (
            Transaction.objects.filter(
                order__in=orders_30_qs, status="success", created_at__gte=since_14
            )
            .annotate(d=TruncDate("created_at"))
            .values("d")
            .annotate(amount=Sum("amount"))
        )
        rev_by_day = {str(r["d"]): float(r["amount"] or 0) for r in tx_14}

        # Build last 14 days series including days with zero values
        series_14d = []
        for i in range(14, 0, -1):
            d = today - timedelta(days=i - 1)
            k = str(d)
            series_14d.append(
                {"date": k, "orders": orders_by_day.get(k, 0), "revenue": rev_by_day.get(k, 0.0)}
            )

        # Optional: last payout (if a payouts app/model exists)
        last_payout = None
        try:
            Payout = apps.get_model("payouts", "Payout")
            last = (
                Payout.objects.filter(vendor_id=owner_id)
                .only("id", "amount", "created_at")
                .order_by("-created_at")
                .first()
            )
            if last:
                last_payout = {
                    "amount": float(getattr(last, "amount", 0) or 0),
                    "created_at": last.created_at.isoformat(),
                }
        except Exception:
            last_payout = None

        return Response(
            {
                "products": {"total": total_products, "live": live_products},
                "orders_30d": orders_30d,
                "revenue_30d": revenue_30d,
                "series_14d": series_14d,
                "last_payout": last_payout,
            }
        )

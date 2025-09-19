from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import VendorMember, VendorOrg
from .permissions import IsInOrg, IsOrgManager, IsOrgOwner, IsOrgStaff
from .serializers_v1 import InviteSerializer, MemberSerializer, OrgSerializer
from .selectors import org_scoped_queryset, get_kpis, get_realtime
from drf_spectacular.utils import extend_schema, OpenApiExample, extend_schema_view
from .permissions import IsOrgManager
from .throttling import VendorOrgScopedRateThrottle

from product_app.models import Product
from product_app.serializers_v1 import ProductV1Serializer
from orders.models import Order, OrderItem
from orders.serializers_v1 import OrderV1Serializer

try:
    # Optional: enrich OpenAPI with tags/operation summaries
    from drf_spectacular.utils import extend_schema, extend_schema_view
except Exception:  # pragma: no cover - spectacular may be absent in some envs
    def extend_schema(*args, **kwargs):  # type: ignore
        def deco(func):
            return func
        return deco

    def extend_schema_view(**kwargs):  # type: ignore
        def deco(cls):
            return cls
        return deco


class DefaultPage(PageNumberPagination):
    page_size = 20
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(tags=["Vendor Orgs"], summary="List my organizations"),
    retrieve=extend_schema(tags=["Vendor Orgs"], summary="Retrieve an organization"),
    create=extend_schema(tags=["Vendor Orgs"], summary="Create an organization"),
    partial_update=extend_schema(tags=["Vendor Orgs"], summary="Update organization"),
    update=extend_schema(tags=["Vendor Orgs"], summary="Replace organization"),
)
class OrgViewSet(viewsets.ModelViewSet):
    serializer_class = OrgSerializer
    pagination_class = DefaultPage
    throttle_classes = [VendorOrgScopedRateThrottle]

    def get_queryset(self) -> QuerySet:
        user = self.request.user
        if not user.is_authenticated:
            return VendorOrg.objects.none()
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return VendorOrg.objects.all().order_by("id")
        return (
            VendorOrg.objects.filter(members__user=user, members__is_active=True)
            .distinct()
            .order_by("id")
        )

    def get_permissions(self):  # type: ignore[override]
        if self.action in {"list", "create"}:
            return [IsAuthenticated()]
        if self.action in {"partial_update", "update"}:  # owner/manager can update tax fields
            return [IsOrgManager()]
        if self.action in {"invite"}:
            return [IsOrgManager()]
        if self.action in {"members", "orders", "products"}:
            return [IsOrgStaff()]
        # retrieve default to membership
        return [IsInOrg()]

    def perform_create(self, serializer):
        user = self.request.user
        with transaction.atomic():
            org = serializer.save(owner=user)
            org.add_member(user, "OWNER")
            # Ensure KRA PIN normalization & validation
            org.full_clean()

    @extend_schema(tags=["Vendor Orgs"], summary="Invite or upsert a member")
    @action(detail=True, methods=["post"], url_path="invite")
    def invite(self, request, pk=None):
        org = self.get_object()
        ser = InviteSerializer(data=request.data, context={"org": org, "request": request})
        ser.is_valid(raise_exception=True)
        member = ser.save()
        return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @extend_schema(tags=["Vendor Members"], summary="List org members")
    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        org = self.get_object()
        qs = VendorMember.objects.filter(org=org).select_related("user").order_by("id")
        page = self.paginate_queryset(qs)
        ser = MemberSerializer(page, many=True)
        return self.get_paginated_response(ser.data)

    @extend_schema(tags=["Vendor Orgs"], summary="List org orders")
    @action(detail=True, methods=["get"], url_path="orders")
    def orders(self, request, pk=None):
        org_id = int(pk)
        # Orders having at least one item whose product belongs to this org
        order_ids = (
            OrderItem.objects.filter(product__owner__vendor_profile__org_id=org_id)
            .values_list("order_id", flat=True)
            .distinct()
        )
        qs = Order.objects.filter(id__in=order_ids).order_by("-created_at")
        page = self.paginate_queryset(qs)
        ser = OrderV1Serializer(page, many=True)
        return self.get_paginated_response(ser.data)

    @extend_schema(tags=["Vendor Orgs"], summary="List org products")
    @action(detail=True, methods=["get"], url_path="products")
    def products(self, request, pk=None):
        qs = org_scoped_queryset(Product.objects.all(), org_id=int(pk)).order_by("id")
        page = self.paginate_queryset(qs)
        ser = ProductV1Serializer(page, many=True)
        return self.get_paginated_response(ser.data)

    @extend_schema(
        tags=["Vendor KPIs"],
        summary="List KPI aggregates",
        examples=[
            OpenApiExample(
                'KPIs Response',
                value={
                    "results": [
                        {"period_start": "2025-09-01", "period_end": "2025-09-01", "window": "daily", "gross_revenue": "1000.00", "net_revenue": "950.00", "orders": 10, "refunds": 1, "success_rate": "90.00", "fulfillment_avg_mins": "45.00"}
                    ]
                },
                response_only=True,
            )
        ],
    )
    @action(detail=True, methods=["get"], url_path="kpis")
    def kpis(self, request, pk=None):
        from django.conf import settings
        if not getattr(settings, "KPIS_ENABLED", False):
            return Response({"detail": "KPIs disabled"}, status=status.HTTP_404_NOT_FOUND)
        # OWNER/MANAGER only
        if not IsOrgManager().has_permission(request, self):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        window = request.query_params.get("window", "daily")
        last_n = int(request.query_params.get("last_n", "30"))
        items = get_kpis(int(pk), window, last_n)
        data = [
            {
                "period_start": str(i.period_start),
                "period_end": str(i.period_end),
                "window": i.window,
                "gross_revenue": str(i.gross_revenue),
                "net_revenue": str(i.net_revenue),
                "orders": i.orders,
                "refunds": i.refunds,
                "success_rate": str(i.success_rate),
                "fulfillment_avg_mins": str(i.fulfillment_avg_mins),
            }
            for i in items
        ]
        return Response({"results": data})

    @extend_schema(
        tags=["Vendor KPIs"],
        summary="Realtime KPI snapshot",
        examples=[
            OpenApiExample(
                'Realtime Snapshot',
                value={"gross_revenue": "100.00", "net_revenue": "95.00", "orders": 1, "refunds": 0},
                response_only=True,
            )
        ],
    )
    @action(detail=True, methods=["get"], url_path="kpis/realtime")
    def kpis_realtime(self, request, pk=None):
        from django.conf import settings
        if not getattr(settings, "KPIS_ENABLED", False):
            return Response({"detail": "KPIs disabled"}, status=status.HTTP_404_NOT_FOUND)
        if not IsOrgManager().has_permission(request, self):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        snap = get_realtime(int(pk))
        # serialize decimals as strings
        snap = {k: (str(v) if hasattr(v, 'quantize') else v) for k, v in snap.items()}
        return Response(snap)


@extend_schema_view(
    retrieve=extend_schema(tags=["Vendor Members"], summary="Get member"),
    destroy=extend_schema(tags=["Vendor Members"], summary="Deactivate member"),
)
class MemberViewSet(mixins.DestroyModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MemberSerializer
    pagination_class = DefaultPage
    throttle_classes = [VendorOrgScopedRateThrottle]

    def get_queryset(self) -> QuerySet:
        user = self.request.user
        if not user.is_authenticated:
            return VendorMember.objects.none()
        return VendorMember.objects.filter(
            org__members__user=user, org__members__is_active=True
        ).select_related("org", "user").order_by("id")

    def destroy(self, request, *args, **kwargs):  # soft-deactivate
        member: VendorMember = self.get_object()
        # Only MANAGER or OWNER of this org may deactivate a member
        if not (request.user and request.user.is_authenticated):
            return Response(status=status.HTTP_403_FORBIDDEN)

        from .services import has_min_role

        if not has_min_role(request.user, member.org, "MANAGER"):
            return Response(status=status.HTTP_403_FORBIDDEN)

        if member.role == VendorMember.Role.OWNER:
            # Disallow deactivating the sole owner
            return Response({"detail": "Cannot deactivate an OWNER."}, status=status.HTTP_400_BAD_REQUEST)

        member.is_active = False
        member.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

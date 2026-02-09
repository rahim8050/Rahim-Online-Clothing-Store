# apis/views.py
from __future__ import annotations

import csv
import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import StringIO
from typing import ClassVar, Sequence, Type

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.core.signing import dumps as sign
from django.core.signing import loads as unsign
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import log_action
from core.permissions import InGroups
from core.siteutils import current_domain
from inventory.services import check_low_stock_and_notify
from payments.enums import Gateway
from payments.services.reconcile import (
    ReconcileConflict,
    ReconcileError,
    reconcile_mpesa,
    reconcile_paystack,
    reconcile_stripe,
)
from orders.models import Delivery, DeliveryEvent, OrderItem
from product_app.models import Product
from product_app.queries import shopable_products_q
from product_app.utils import get_vendor_field
from users.constants import DRIVER
from users.models import VendorApplication, VendorStaff
from users.permissions import (
    HasVendorScope,
    IsDriver,
    IsVendorOrVendorStaff,
    IsVendorOwner,
)
from users.services import activate_vendor_staff  # group sync helper
from users.utils import resolve_vendor_owner_for, vendor_owner_ids_for

from .serializers import (
    DeliveryAssignSerializer,
    DeliverySerializer,
    DeliveryStatusSerializer,
    DeliveryUnassignSerializer,
    ProductListSerializer,
    ProductOutSerializer,
    ProductSerializer,
    VendorApplicationCreateSerializer,
    VendorProductCreateSerializer,
    VendorStaffCreateSerializer,
    VendorStaffInviteSerializer,
    VendorStaffOutSerializer,
    VendorStaffRemoveSerializer,
    PaymentReconcileRequestSerializer,
    PaymentReconcileResponseSerializer,
    WhoAmISerializer,
    _EmptySerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()
signer = TimestampSigner()
Q6 = Decimal("0.000001")


# --------- Doc helper serializers (module-level to avoid nested scope issues) ---------
class VendorProductsImportRequestSerializer(serializers.Serializer):
    owner_id = serializers.IntegerField(required=False)
    file = serializers.FileField()


class VendorProductsImportResultErrorSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    error = serializers.CharField()


class VendorProductsImportResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    error_items = VendorProductsImportResultErrorSerializer(many=True)


# ----------------------- Auth mixins -----------------------
class SessionJWTAuthMixin:
    authentication_classes: ClassVar[Sequence[Type[BaseAuthentication]]] = (
        SessionAuthentication,
        JWTAuthentication,
    )


class SessionJWTAPIView(SessionJWTAuthMixin, APIView):
    pass


class SessionJWTListAPIView(SessionJWTAuthMixin, ListAPIView):
    pass


class SessionJWTCreateAPIView(SessionJWTAuthMixin, CreateAPIView):
    pass


# ----------------------- Helpers -----------------------
def _publish_delivery(
    delivery: Delivery, kind: str, payload: dict | None = None
) -> None:
    """Publish a generic delivery event to the delivery's WS group."""
    layer = get_channel_layer()
    if not layer:
        return
    data = {"type": "delivery.event", "kind": kind, "delivery_id": delivery.pk}
    if payload:
        data.update(payload)
    async_to_sync(layer.group_send)(delivery.ws_group, data)


def _publish_vendor(owner_id: int, kind: str, payload: dict | None = None) -> None:
    """Send an event to a vendor owner group."""
    layer = get_channel_layer()
    if not layer:
        return
    data = {"type": "vendor.event", "t": kind}
    if payload:
        data.update(payload)
    async_to_sync(layer.group_send)(f"vendor.{owner_id}", data)


def orderitem_reverse_name() -> str:
    rel_name = OrderItem._meta.get_field("product").remote_field.related_name
    if rel_name == "+":
        return ""
    return rel_name or "orderitem_set"


def _q6(x) -> Decimal:
    # robust quantize for coords
    return Decimal(str(x)).quantize(Q6, rounding=ROUND_HALF_UP)


# ----------------------- Who am I -----------------------
class WhoAmI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WhoAmISerializer  # for schema generation

    @extend_schema(request=None, responses=WhoAmISerializer)
    def get(self, request):
        ser = WhoAmISerializer(request.user)
        return Response(ser.data)


# ----------------------- Products (shop & vendor) -----------------------
class ShopablePagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 50


class ShopableProductsAPI(SessionJWTListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = ShopablePagination

    def get_queryset(self):
        qs = Product.objects.filter(available=True)
        u = self.request.user
        if u.is_authenticated:
            qs = qs.filter(shopable_products_q(u))
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        return qs


class VendorProductsAPI(SessionJWTAPIView):
    """
    Returns products for the vendor owner context of the caller.
    - Vendor owner: sees their own products
    - Vendor staff: sees selected owner's products (owner_id) or raises if multiple allowed
    """

    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff]
    serializer_class = ProductSerializer  # response

    @extend_schema(request=None, responses=ProductSerializer(many=True))
    def get(self, request):
        raw_owner = request.query_params.get("owner_id")
        try:
            owner_id = resolve_vendor_owner_for(
                request.user, raw_owner, require_explicit_if_multiple=True
            )
        except ValueError as e:
            return Response({"owner_id": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        field = get_vendor_field(Product)  # e.g. "vendor" or "owner"
        vendor_field_id = f"{field}_id"

        try:
            base_qs = Product.objects.filter(**{vendor_field_id: owner_id})
        except Exception:
            logger.warning(
                "Product model missing vendor field '%s'", field, exc_info=True
            )
            base_qs = Product.objects.none()

        q = request.query_params.get("q")
        if q:
            base_qs = base_qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        rev = orderitem_reverse_name()
        if rev:
            oi_qs = OrderItem.objects.select_related("order", "product").only(
                "id", "order_id", "product_id", "price", "quantity", "delivery_status"
            )
            products = base_qs.prefetch_related(Prefetch(rev, queryset=oi_qs))
        else:
            products = base_qs

        serializer = ProductSerializer(
            products, many=True, context={"request": request}
        )
        return Response(serializer.data)


# ----------------------- Deliveries -----------------------
class DriverDeliveriesAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, IsDriver]
    serializer_class = DeliverySerializer

    @extend_schema(request=None, responses=DeliverySerializer(many=True))
    def get(self, request):
        qs = (
            Delivery.objects.filter(driver=request.user)
            .select_related("order")
            .order_by("-id")
        )
        serializer = DeliverySerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


class VendorDeliveriesAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff]

    class VendorDeliveryOutSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        order_id = serializers.IntegerField()
        driver_id = serializers.IntegerField(allow_null=True)
        status = serializers.CharField()
        assigned_at = serializers.DateTimeField(allow_null=True)
        picked_up_at = serializers.DateTimeField(allow_null=True)
        delivered_at = serializers.DateTimeField(allow_null=True)
        last_lat = serializers.FloatField(allow_null=True)
        last_lng = serializers.FloatField(allow_null=True)
        last_ping_at = serializers.DateTimeField(allow_null=True)

    serializer_class = VendorDeliveryOutSerializer

    @extend_schema(request=None, responses=VendorDeliveryOutSerializer(many=True))
    def get(self, request):
        raw_owner = request.query_params.get("owner_id")
        try:
            owner_id = resolve_vendor_owner_for(request.user, raw_owner)
        except ValueError as e:
            return Response({"owner_id": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        ProductModel = apps.get_model("product_app", "Product")
        field = get_vendor_field(ProductModel)  # e.g., "owner" or "vendor"
        vendor_field = f"order__items__product__{field}_id"

        qs = (
            Delivery.objects.filter(**{vendor_field: owner_id})
            .select_related("order", "driver")
            .distinct()
            .order_by("-updated_at")
        )

        data = [
            {
                "id": d.id,
                "order_id": d.order_id,
                "driver_id": d.driver_id,
                "status": d.status,
                "assigned_at": d.assigned_at and d.assigned_at.isoformat(),
                "picked_up_at": d.picked_up_at and d.picked_up_at.isoformat(),
                "delivered_at": d.delivered_at and d.delivered_at.isoformat(),
                "last_lat": float(d.last_lat) if d.last_lat is not None else None,
                "last_lng": float(d.last_lng) if d.last_lng is not None else None,
                "last_ping_at": d.last_ping_at and d.last_ping_at.isoformat(),
            }
            for d in qs[:300]
        ]
        return Response(data)


class DeliveryAssignAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff, HasVendorScope]
    required_vendor_scope = "delivery"
    serializer_class = DeliveryAssignSerializer

    @extend_schema(request=DeliveryAssignSerializer, responses=DeliverySerializer)
    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk)
        ser = DeliveryAssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        driver = get_object_or_404(User, pk=ser.validated_data["driver_id"])

        delivery.mark_assigned(driver)
        delivery.save(update_fields=["driver", "status", "assigned_at"])

        try:
            DeliveryEvent.objects.create(
                delivery=delivery,
                actor=request.user,
                type="assign",
                note={"driver_id": driver.id},
            )
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        try:
            owner_id = getattr(
                delivery.order.items.first().product,
                get_vendor_field(Product) + "_id",
                None,
            )
            log_action(
                request.user,
                owner_id,
                "delivery.assign",
                "delivery",
                delivery.id,
                {"driver_id": driver.id},
            )
            if owner_id:
                _publish_vendor(owner_id, "delivery.assigned", {"rid": delivery.id})
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        _publish_delivery(delivery, "assign", {"driver_id": driver.id})
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DeliveryUnassignAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff, HasVendorScope]
    required_vendor_scope = "delivery"
    serializer_class = DeliveryUnassignSerializer  # empty serializer for docs

    @extend_schema(request=DeliveryUnassignSerializer, responses=DeliverySerializer)
    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk)
        delivery.driver = None
        delivery.status = Delivery.Status.PENDING
        delivery.assigned_at = None
        delivery.save(update_fields=["driver", "status", "assigned_at"])

        try:
            DeliveryEvent.objects.create(
                delivery=delivery, actor=request.user, type="unassign"
            )
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        try:
            owner_id = getattr(
                delivery.order.items.first().product,
                get_vendor_field(Product) + "_id",
                None,
            )
            log_action(
                request.user, owner_id, "delivery.unassign", "delivery", delivery.id
            )
            if owner_id:
                _publish_vendor(owner_id, "delivery.unassigned", {"rid": delivery.id})
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        _publish_delivery(delivery, "unassign", {"driver_id": None})
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DeliveryAcceptAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [DRIVER]
    serializer_class = _EmptySerializer  # no request body

    @extend_schema(request=None, responses=DeliverySerializer)
    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, driver__isnull=True)
        delivery.mark_assigned(request.user)
        delivery.save(update_fields=["driver", "status", "assigned_at"])
        _publish_delivery(delivery, "accept", {"driver_id": request.user.id})
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DeliveryStatusAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [DRIVER]
    serializer_class = DeliveryStatusSerializer

    @extend_schema(request=DeliveryStatusSerializer, responses=DeliverySerializer)
    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, driver=request.user)
        ser = DeliveryStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_status = ser.validated_data["status"]

        delivery.status = new_status
        if new_status == Delivery.Status.PICKED_UP:
            delivery.picked_up_at = timezone.now()
            try:
                DeliveryEvent.objects.create(
                    delivery=delivery, actor=request.user, type="picked"
                )
            except Exception as e:
                logger.exception(
                    "Non-critical side-effect failed in %s: %s", __name__, e
                )

        elif new_status == Delivery.Status.DELIVERED:
            delivery.delivered_at = timezone.now()
            try:
                DeliveryEvent.objects.create(
                    delivery=delivery, actor=request.user, type="delivered"
                )
            except Exception as e:
                logger.exception(
                    "Non-critical side-effect failed in %s: %s", __name__, e
                )

        delivery.save(update_fields=["status", "picked_up_at", "delivered_at"])
        _publish_delivery(delivery, "status", {"status": new_status})
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DriverLocationAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [DRIVER]

    class DriverLocationInSerializer(serializers.Serializer):
        delivery_id = serializers.IntegerField()
        lat = serializers.DecimalField(max_digits=9, decimal_places=6)
        lng = serializers.DecimalField(max_digits=9, decimal_places=6)

    class DriverLocationOutSerializer(serializers.Serializer):
        ok = serializers.BooleanField()
        status = serializers.CharField()
        ts = serializers.DateTimeField()

    serializer_class = DriverLocationInSerializer

    @extend_schema(
        request=DriverLocationInSerializer, responses=DriverLocationOutSerializer
    )
    def post(self, request):
        delivery_id = request.data.get("delivery_id")
        try:
            delivery_id = int(delivery_id)
        except (TypeError, ValueError):
            return Response(
                {"detail": "delivery_id required (int)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            lat = _q6(request.data.get("lat"))
            lng = _q6(request.data.get("lng"))
        except (InvalidOperation, TypeError, ValueError):
            return Response(
                {"detail": "lat/lng must be numeric"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (
            Decimal("-90") <= lat <= Decimal("90")
            and Decimal("-180") <= lng <= Decimal("180")
        ):
            return Response(
                {"detail": "lat/lng out of range"}, status=status.HTTP_400_BAD_REQUEST
            )

        delivery = get_object_or_404(Delivery, pk=delivery_id, driver=request.user)

        now = timezone.now()
        delivery.last_lat = lat
        delivery.last_lng = lng
        delivery.last_ping_at = now
        delivery.save(
            update_fields=["last_lat", "last_lng", "last_ping_at", "updated_at"]
        )

        _publish_delivery(
            delivery,
            "position_update",
            {"lat": float(lat), "lng": float(lng), "ts": now.isoformat()},
        )
        return Response({"ok": True, "status": "updated", "ts": now.isoformat()})


# ----------------------- Products (create/import/export) -----------------------
class VendorProductCreateAPI(SessionJWTCreateAPIView):
    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff]
    serializer_class = VendorProductCreateSerializer

    def create(self, request, *args, **kwargs):
        in_ser = self.get_serializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        product = in_ser.save()

        out_ser = ProductOutSerializer(product, context={"request": request})
        headers = {
            "Location": reverse(
                "product_app:product_detail",
                kwargs={"id": product.id, "slug": product.slug},
            )
        }
        try:
            owner_id = getattr(product, get_vendor_field(Product) + "_id", None)
            log_action(request.user, owner_id, "product.create", "product", product.id)
            check_low_stock_and_notify(product)
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        return Response(out_ser.data, status=status.HTTP_201_CREATED, headers=headers)


class VendorProductsImportCSV(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff, HasVendorScope]
    required_vendor_scope = "catalog"
    serializer_class = VendorProductsImportRequestSerializer

    @extend_schema(
        request=VendorProductsImportRequestSerializer,
        responses=VendorProductsImportResultSerializer,
    )
    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "file required"}, status=400)
        try:
            buf = f.read().decode("utf-8", errors="replace")
        except Exception:
            return Response({"detail": "unable to read file"}, status=400)

        reader = csv.DictReader(StringIO(buf))

        def norm(value: str | None) -> str:
            return (value or "").strip().lower()

        wanted = {"name", "sku", "price", "stock", "published"}
        header = {norm(h): h for h in (reader.fieldnames or [])}
        if not wanted.issubset(set(header.keys())):
            return Response(
                {"detail": "missing columns", "required": sorted(list(wanted))},
                status=400,
            )

        try:
            owner_id = resolve_vendor_owner_for(
                request.user, request.data.get("owner_id")
            )
        except ValueError as e:
            return Response({"owner_id": str(e)}, status=400)

        created = 0
        updated = 0
        errors = []
        field = get_vendor_field(Product)

        for i, row in enumerate(reader, start=2):
            try:
                name = (row.get(header["name"]) or "").strip()
                sku = (row.get(header["sku"]) or name).strip()
                price = str(row.get(header["price"]) or "0").strip()
                published = str(row.get(header["published"]) or "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                )
                if not name:
                    raise ValueError("name required")

                obj, was_created = Product.objects.update_or_create(
                    **{f"{field}_id": owner_id, "slug": sku.lower().replace(" ", "-")},
                    defaults={"name": name, "price": price, "available": published},
                )
                created += int(was_created)
                updated += int(not was_created)
            except Exception as e:
                errors.append({"row": i, "error": str(e)})

        return Response(
            {
                "created": created,
                "updated": updated,
                "errors": errors,
                "error_items": errors,
            }
        )


class VendorProductsExportCSV(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff, HasVendorScope]
    required_vendor_scope = "catalog"
    serializer_class = _EmptySerializer

    @extend_schema(request=None, responses={(200, "text/csv"): OpenApiTypes.STR})
    def get(self, request):
        try:
            owner_id = resolve_vendor_owner_for(
                request.user, request.query_params.get("owner_id")
            )
        except ValueError as e:
            return Response({"owner_id": str(e)}, status=400)

        field = get_vendor_field(Product)
        qs = Product.objects.filter(**{f"{field}_id": owner_id}).only(
            "id", "name", "slug", "price", "available"
        )

        out = StringIO()
        w = csv.writer(out)
        w.writerow(["name", "sku", "price", "stock", "published"])
        for p in qs:
            w.writerow([p.name, "", p.price, "", str(bool(p.available)).lower()])

        return Response(out.getvalue(), content_type="text/csv")


# ----------------------- Vendor Staff (invite/accept/list/remove/deactivate) -----------------------
class VendorStaffInviteAPI(SessionJWTAPIView):
    permission_classes = [permissions.IsAuthenticated, IsVendorOwner]
    serializer_class = VendorStaffInviteSerializer

    class VendorStaffInviteOutSerializer(serializers.Serializer):
        ok = serializers.BooleanField()
        message = serializers.CharField()
        payload = serializers.DictField()

    @extend_schema(
        request=VendorStaffInviteSerializer, responses=VendorStaffInviteOutSerializer
    )
    def post(self, request):
        ser = VendorStaffInviteSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)

        owner_id = ser.validated_data["owner_id"]
        staff = ser.validated_data["staff"]

        with transaction.atomic():
            vs, created = VendorStaff.objects.select_for_update().get_or_create(
                owner_id=owner_id, staff=staff, defaults={"is_active": False}
            )

            if vs.is_active:
                return Response(
                    {"detail": "Staff is already active for this owner."},
                    status=status.HTTP_409_CONFLICT,
                )

            token = sign({"vs_id": vs.id, "staff_id": staff.id})
            path = reverse("vendor-staff-accept", args=[token])
            invite_link = request.build_absolute_uri(path)

            if created:
                domain = current_domain(request)
                site_name = getattr(settings, "SITE_NAME", domain)
                subject = f"You're invited to join {site_name}"
                html_content = render_to_string(
                    "emails/vendor_staff_invite.html",
                    {
                        "staff": staff,
                        "owner": request.user,
                        "invite_link": invite_link,
                        "site_name": site_name,
                        "support_email": getattr(
                            settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL
                        ),
                    },
                )
                text_content = f"You've been invited as vendor staff.\n\nAccept your invite: {invite_link}"

                def _send():
                    try:
                        email = EmailMultiAlternatives(
                            subject=subject,
                            body=text_content,
                            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                            to=[staff.email],
                        )
                        email.attach_alternative(html_content, "text/html")
                        email.send(fail_silently=False)
                        logger.info(
                            "Invite email sent to %s (vs=%s)", staff.email, vs.id
                        )
                    except Exception as e:
                        logger.exception("Invite email failed for vs=%s: %s", vs.id, e)

                transaction.on_commit(_send)

        try:
            log_action(request.user, owner_id, "staff.invite", "user", staff.id)
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        payload = {
            "vendor_staff_id": vs.id,
            "owner_id": vs.owner_id,
            "staff_id": vs.staff_id,
            "is_active": vs.is_active,
            "invite_link_preview": invite_link if created else None,
        }
        return Response(
            {
                "ok": True,
                "message": (
                    "Invite created and email queued."
                    if created
                    else "Invite already pending."
                ),
                "data": payload,
                "payload": payload,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class VendorStaffAcceptAPI(SessionJWTAPIView):
    permission_classes = [permissions.IsAuthenticated]
    TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
    serializer_class = _EmptySerializer

    class VendorStaffAcceptOutSerializer(serializers.Serializer):
        ok = serializers.BooleanField()
        message = serializers.CharField()

    @extend_schema(request=None, responses=VendorStaffAcceptOutSerializer)
    def post(self, request, token: str):
        try:
            payload = unsign(token, max_age=self.TOKEN_MAX_AGE)
        except SignatureExpired:
            return Response({"detail": "Invite link expired."}, status=410)
        except BadSignature:
            return Response({"detail": "Invalid invite link."}, status=400)

        vs_id = payload.get("vs_id")
        staff_id = payload.get("staff_id")
        if not vs_id or not staff_id:
            return Response({"detail": "Malformed invite token."}, status=400)

        if request.user.id != staff_id:
            return Response(
                {"detail": "This invite is not for the current user."}, status=403
            )

        with transaction.atomic():
            try:
                vs = VendorStaff.objects.select_for_update().get(
                    pk=vs_id, staff_id=staff_id
                )
            except VendorStaff.DoesNotExist:
                return Response({"detail": "Invite not found."}, status=404)

            if vs.is_active:
                return Response({"detail": "Already accepted."}, status=200)

            vs.is_active = True
            vs.save(update_fields=["is_active"])

        try:
            activate_vendor_staff(request.user, vs.owner_id)
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        try:
            log_action(request.user, vs.owner_id, "staff.accept", "vendorstaff", vs.id)
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        return Response({"ok": True, "message": "Invite accepted."}, status=200)


class VendorStaffListCreateView(SessionJWTAPIView):
    permission_classes = [permissions.IsAuthenticated, IsVendorOwner]
    serializer_class = VendorStaffCreateSerializer  # request body for POST

    @extend_schema(request=None, responses=VendorStaffOutSerializer(many=True))
    def get(self, request):
        raw_owner = request.query_params.get("owner_id")
        try:
            owner_id = resolve_vendor_owner_for(request.user, raw_owner)
        except ValueError as e:
            return Response({"owner_id": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        qs = VendorStaff.objects.filter(owner_id=owner_id).order_by("-id")
        return Response(VendorStaffOutSerializer(qs, many=True).data)

    @extend_schema(
        request=VendorStaffCreateSerializer, responses=VendorStaffOutSerializer
    )
    def post(self, request):
        raw_owner = request.data.get("owner_id")
        try:
            owner_id = resolve_vendor_owner_for(request.user, raw_owner)
        except ValueError as e:
            return Response({"owner_id": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        payload = dict(request.data)
        payload["owner_id"] = owner_id
        ser = VendorStaffCreateSerializer(data=payload, context={"request": request})
        ser.is_valid(raise_exception=True)
        row = ser.save()
        try:
            log_action(request.user, owner_id, "staff.create", "vendorstaff", row.id)
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        return Response(
            VendorStaffOutSerializer(row).data, status=status.HTTP_201_CREATED
        )


class VendorStaffRemoveAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, IsVendorOwner]
    serializer_class = VendorStaffRemoveSerializer

    class VendorStaffRemoveOutSerializer(serializers.Serializer):
        ok = serializers.BooleanField()

    @extend_schema(
        request=VendorStaffRemoveSerializer, responses=VendorStaffRemoveOutSerializer
    )
    def post(self, request, staff_id: int | None = None):
        payload = dict(request.data)
        if staff_id is not None and not payload.get("staff_id"):
            payload["staff_id"] = staff_id

        ser = VendorStaffRemoveSerializer(data=payload, context={"request": request})
        ser.is_valid(raise_exception=True)
        data = ser.save()

        try:
            raw_owner = request.data.get("owner_id")
            owner_id = resolve_vendor_owner_for(request.user, raw_owner)
            log_action(
                request.user,
                owner_id,
                "staff.remove",
                "user",
                ser.validated_data.get("staff_id"),
            )
        except Exception as e:
            logger.exception("Non-critical side-effect failed in %s: %s", __name__, e)

        return Response(data)


class VendorStaffDeactivateAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, IsVendorOwner]
    serializer_class = _EmptySerializer

    class VendorStaffDeactivateOutSerializer(serializers.Serializer):
        ok = serializers.BooleanField()

    @extend_schema(request=None, responses=VendorStaffDeactivateOutSerializer)
    def post(self, request, staff_id: int):
        from users.services import deactivate_vendor_staff

        try:
            owner_id = resolve_vendor_owner_for(
                request.user, request.data.get("owner_id")
            )
        except ValueError as e:
            return Response({"owner_id": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            staff = get_object_or_404(User, pk=staff_id)
            deactivate_vendor_staff(staff, owner_id)
            log_action(request.user, owner_id, "staff.deactivate", "user", staff_id)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"ok": True})


# ----------------------- Vendor Application -----------------------
class VendorApplyAPI(SessionJWTAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = VendorApplicationCreateSerializer

    class VendorApplyOutSerializer(serializers.Serializer):
        status = serializers.CharField()
        id = serializers.IntegerField()
        created = serializers.BooleanField()

    @transaction.atomic
    @extend_schema(
        request=VendorApplicationCreateSerializer, responses=VendorApplyOutSerializer
    )
    def post(self, request):
        user = request.user

        # 1) Block if already vendor/staff
        is_vendor_group = user.groups.filter(
            name__in=["Vendor", "Vendor Staff"]
        ).exists()
        if (
            is_vendor_group
            or VendorStaff.objects.filter(staff=user, is_active=True).exists()
        ):
            return Response(
                {"detail": "Already a vendor/staff."}, status=status.HTTP_409_CONFLICT
            )
        # Also block if a previous application was approved
        if VendorApplication.objects.filter(
            user=user, status=VendorApplication.APPROVED
        ).exists():
            return Response(
                {"detail": "Already approved as vendor."},
                status=status.HTTP_409_CONFLICT,
            )

        # 2) Validate payload
        ser = VendorApplicationCreateSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)

        # 3) Idempotent pending app per user
        try:
            app, created = VendorApplication.objects.get_or_create(
                user=user,
                status=VendorApplication.PENDING,
                defaults=ser.validated_data,
            )
        except Exception:
            app = (
                VendorApplication.objects.filter(
                    user=user, status=VendorApplication.PENDING
                )
                .order_by("-id")
                .first()
            )
            created = False

        return Response(
            {"status": "pending", "id": app.id, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class VendorApplyStatusAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = _EmptySerializer

    class VendorApplyStatusOutSerializer(serializers.Serializer):
        has_applied = serializers.BooleanField()
        status = serializers.CharField(allow_null=True)
        application_id = serializers.IntegerField(allow_null=True)

    @extend_schema(request=None, responses=VendorApplyStatusOutSerializer)
    def get(self, request):
        app = (
            VendorApplication.objects.filter(user=request.user)
            .order_by("-id")
            .values("id", "status")
            .first()
        )
        return Response(
            {
                "has_applied": bool(app),
                "status": app["status"] if app else None,
                "application_id": app["id"] if app else None,
            }
        )


# ----------------------- Vendor owners list (for UI pickers) -----------------------
class VendorOwnersAPI(SessionJWTAPIView):
    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff]

    class VendorOwnerOutSerializer(serializers.Serializer):
        id = serializers.IntegerField()
        name = serializers.CharField()

    serializer_class = _EmptySerializer

    @extend_schema(request=None, responses=VendorOwnerOutSerializer(many=True))
    def get(self, request):
        ids = list(vendor_owner_ids_for(request.user))
        if not ids:
            return Response([])
        rows = User.objects.filter(id__in=ids).only(
            "id", "first_name", "last_name", "email"
        )
        data = [
            {"id": u.id, "name": (u.get_full_name() or u.email or str(u.id))}
            for u in rows
        ]
        return Response(sorted(data, key=lambda x: x["name"].lower()))


# -----------------------
# Payments reconciliation
# -----------------------
class PaymentReconcileAPI(SessionJWTAPIView):
    permission_classes = [permissions.IsAdminUser]
    serializer_class = PaymentReconcileRequestSerializer

    @extend_schema(
        request=PaymentReconcileRequestSerializer,
        responses={200: PaymentReconcileResponseSerializer},
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        gateway_value = serializer.validated_data["gateway"]
        reference = serializer.validated_data["ref"]

        try:
            gateway = Gateway(gateway_value)
        except ValueError:
            return Response(
                {
                    "ok": False,
                    "code": "invalid_gateway",
                    "detail": "Unsupported gateway supplied.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        handler = {
            Gateway.PAYSTACK: reconcile_paystack,
            Gateway.MPESA: reconcile_mpesa,
            Gateway.STRIPE: reconcile_stripe,
        }[gateway]

        logger.info(
            "payments.reconcile.request",
            extra={
                "gateway": gateway.value,
                "reference": reference,
                "user": request.user.id,
            },
        )

        try:
            result = handler(reference)
        except ReconcileConflict as exc:
            payload = {"ok": False, "code": exc.code, "detail": exc.message}
            if exc.extra:
                payload.update(exc.extra)
            return Response(payload, status=exc.status_code)
        except ReconcileError as exc:
            payload = {"ok": False, "code": exc.code, "detail": exc.message}
            if exc.extra:
                payload.update(exc.extra)
            return Response(payload, status=exc.status_code)

        result.setdefault("ok", True)
        result.setdefault("gateway", gateway.value)
        result.setdefault("cached", False)
        return Response(result, status=status.HTTP_200_OK)

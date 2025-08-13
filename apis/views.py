# apis/views.py
from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import (
    ProductSerializer,
    DeliverySerializer,
    DeliveryAssignSerializer,
    DeliveryUnassignSerializer,
    DeliveryStatusSerializer,
    ProductListSerializer,
    VendorProductCreateSerializer,
    VendorStaffInviteSerializer,
    VendorStaffRemoveSerializer,
    VendorApplySerializer,
)
from .permissions import InGroups
from .utils import shopable_products_q
from product_app.models import Product
from product_app.utils import get_vendor_field
from orders.models import Delivery, OrderItem
from users.roles import ROLE_VENDOR, ROLE_VENDOR_STAFF, ROLE_DRIVER

import logging
logger = logging.getLogger(__name__)
User = get_user_model()


def orderitem_reverse_name() -> str:
    """
    Resolve the reverse accessor from Product -> OrderItem at runtime.
    - If OrderItem.product.related_name is None (default), it's 'orderitem_set'.
    - If related_name is '+', reverse relation is disabled -> return ''.
    """
    rel_name = OrderItem._meta.get_field("product").remote_field.related_name
    if rel_name == "+":
        return ""  # reverse disabled
    return rel_name or "orderitem_set"


# ---------- APIs ----------


class ShopablePagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "page_size"
    max_page_size = 50


class ShopableProductsAPI(ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = ShopablePagination

    def get_queryset(self):
        qs = Product.objects.filter(available=True)
        u = self.request.user
        if u.is_authenticated:
            qs = qs.filter(shopable_products_q(u, Product))
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        return qs
class VendorProductsAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_VENDOR, ROLE_VENDOR_STAFF]

    def get(self, request):
        field = get_vendor_field(Product)
        try:
            base_qs = Product.objects.filter(**{field: request.user})
        except Exception:
            logger.warning("Product model missing vendor field '%s'", field, exc_info=True)
            base_qs = Product.objects.none()

        # Prefetch order items efficiently (regardless of related_name)
        rev = orderitem_reverse_name()
        if rev:
            oi_qs = (
                OrderItem.objects
                .select_related("order", "product")
                .only("id", "order_id", "product_id", "price", "quantity", "delivery_status")
            )
            products = base_qs.prefetch_related(Prefetch(rev, queryset=oi_qs))
        else:
            products = base_qs  # reverse disabled via related_name='+'

        serializer = ProductSerializer(products, many=True, context={"request": request})
        return Response(serializer.data)


class DriverDeliveriesAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_DRIVER]

    def get(self, request):
        qs = Delivery.objects.filter(driver=request.user).select_related("order").order_by("-id")
        serializer = DeliverySerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


class DeliveryAssignAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_VENDOR, ROLE_VENDOR_STAFF]

    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk)
        ser = DeliveryAssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        driver = get_object_or_404(User, pk=ser.validated_data["driver_id"])
        delivery.mark_assigned(driver)
        delivery.save(update_fields=["driver", "status", "assigned_at"])
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DeliveryUnassignAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_VENDOR, ROLE_VENDOR_STAFF]

    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk)
        delivery.driver = None
        delivery.status = Delivery.Status.PENDING
        delivery.assigned_at = None
        delivery.save(update_fields=["driver", "status", "assigned_at"])
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DeliveryAcceptAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_DRIVER]

    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, driver__isnull=True)
        delivery.mark_assigned(request.user)
        delivery.save(update_fields=["driver", "status", "assigned_at"])
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DeliveryStatusAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_DRIVER]

    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, driver=request.user)
        ser = DeliveryStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        status = ser.validated_data["status"]
        delivery.status = status
        if status == Delivery.Status.PICKED_UP:
            delivery.picked_up_at = timezone.now()
        if status == Delivery.Status.DELIVERED:
            delivery.delivered_at = timezone.now()
        delivery.save(update_fields=["status", "picked_up_at", "delivered_at"])
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DriverLocationAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_DRIVER]

    def post(self, request):
        lat = request.data.get("lat")
        lng = request.data.get("lng")
        logger.info("Driver %s location lat=%s lng=%s", request.user.pk, lat, lng)
        return Response({"ok": True})
class VendorProductCreateAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_VENDOR, ROLE_VENDOR_STAFF]

    def post(self, request):
        ser = VendorProductCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        product = ser.save()
        return Response({"ok": True, "id": product.id})
    
class VendorStaffInviteAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_VENDOR, ROLE_VENDOR_STAFF]

    def post(self, request):
        ser = VendorStaffInviteSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        vs = ser.save()
        return Response({"ok": True, "owner": vs.owner_id, "staff": vs.staff_id})

class VendorStaffRemoveAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_VENDOR, ROLE_VENDOR_STAFF]

    def post(self, request):
        ser = VendorStaffRemoveSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        data = ser.save()
        return Response(data)
class VendorApplyAPI(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        # Prevent duplicate pending apps
        if apps.get_model("users","VendorApplication").objects.filter(user=request.user, status="pending").exists():
            return Response({"detail":"You already have a pending application."}, status=400)
        ser = VendorApplySerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        app = ser.save()
        return Response({"ok": True, "application_id": app.id})
    
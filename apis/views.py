from django.apps import apps
from django.db.models import Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .permissions import InGroups
from .serializers import ProductSerializer, DeliverySerializer
from product_app.utils import get_vendor_field
from product_app.models import Product
from orders.models import OrderItem
from users.roles import ROLE_VENDOR, ROLE_VENDOR_STAFF, ROLE_DRIVER

import logging
logger = logging.getLogger(__name__)


def safe_get_model(app_label: str, model_name: str):
    """Return model class or None if missing."""
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def orderitem_reverse_name() -> str:
    """
    Resolve the reverse accessor from Product -> OrderItem at runtime.
    If OrderItem.product has related_name=None (default), it's 'orderitem_set'.
    If related_name='+', reverse relation is disabled (we then skip prefetch).
    """
    rel_name = OrderItem._meta.get_field("product").remote_field.related_name
    if rel_name == "+":
        return ""  # no reverse relation
    return rel_name or "orderitem_set"


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
            oi_qs = OrderItem.objects.select_related("order", "product")
            products = base_qs.prefetch_related(Prefetch(rev, queryset=oi_qs))
        else:
            # Reverse disabled via related_name='+'
            products = base_qs

        data = ProductSerializer(products, many=True).data
        return Response(data)


class DriverDeliveriesAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_DRIVER]

    def get(self, request):
        DeliveryModel = safe_get_model("orders", "Delivery")

        # DeliverySerializer in your serializers.py is a no-op EmptySerializer when model is absent.
        serializer_has_model = getattr(getattr(DeliverySerializer, "Meta", None), "model", None) is not None

        if DeliveryModel is None or not serializer_has_model:
            logger.info("Delivery model missing; returning empty list for driver=%s", request.user.pk)
            return Response([])

        deliveries = (
            DeliveryModel.objects
            .filter(driver=request.user)
            .select_related("driver")         # keep if FK exists
            .select_related("order")          # keep if FK exists
        )

        data = DeliverySerializer(deliveries, many=True).data
        return Response(data)

# apis/views.py
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Prefetch, Q
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
User = get_user_model()

# ---------- Utilities ----------
def safe_get_model(app_label: str, model_name: str):
    """Return model class or None if missing."""
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


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


def _build_driver_q(model, user):
    """
    Build a broad Q() that matches any FK/O2O on `model` that resolves to AUTH_USER_MODEL,
    including one hop via a profile model (e.g., courier.user / rider.account).
    """
    q = Q()

    # Heuristic common names to try even if not introspectable.
    candidate_names = {"driver", "assigned_driver", "courier", "rider", "assigned_to", "owner", "user"}

    # 1) Add any *actual* direct relations Delivery.<field> -> User discovered via introspection
    for f in model._meta.get_fields():
        rel_model = getattr(getattr(f, "remote_field", None), "model", None)
        name = getattr(f, "name", None)
        if name and rel_model is User:
            candidate_names.add(name)

    # 2) Indirect: Delivery.<field> -> Profile.<user_like>
    user_like_names = {"user", "account", "owner", "created_by"}

    for name in list(candidate_names):
        try:
            f = model._meta.get_field(name)
        except FieldDoesNotExist:
            continue

        rel_model = getattr(f, "related_model", None)
        # Direct Delivery.<name> -> User
        if rel_model is User:
            q |= Q(**{name: user})
            continue

        # Indirect Delivery.<name> -> Profile.<user_like> -> User
        if rel_model is not None:
            for ul in user_like_names:
                try:
                    rf = rel_model._meta.get_field(ul)
                except FieldDoesNotExist:
                    continue
                if getattr(rf, "related_model", None) is User:
                    q |= Q(**{f"{name}__{ul}": user})

    return q


# ---------- APIs ----------
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
        DeliveryModel = safe_get_model("orders", "Delivery")

        # DeliverySerializer is an EmptySerializer placeholder if model is absent.
        serializer_has_model = getattr(getattr(DeliverySerializer, "Meta", None), "model", None) is not None

        if DeliveryModel is None or not serializer_has_model:
            logger.info("Delivery model missing; returning empty list for driver=%s", request.user.pk)
            return Response([])

        q = _build_driver_q(DeliveryModel, request.user)
        if not q:  # no user-linked relation detected
            logger.warning("No User-linked driver relation detected on Delivery; empty result.")
            qs = DeliveryModel.objects.none()
        else:
            qs = (
                DeliveryModel.objects
                .filter(q)
                .select_related("order")  # cheap access to order if FK exists
                .order_by("-id")
            )

        serializer = DeliverySerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

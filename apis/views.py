from django.apps import apps
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .permissions import InGroups
from .serializers import ProductSerializer, DeliverySerializer
from product_app.utils import get_vendor_field
from product_app.models import Product
from users.roles import ROLE_VENDOR, ROLE_VENDOR_STAFF, ROLE_DRIVER
import logging

logger = logging.getLogger(__name__)

class VendorProductsAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_VENDOR, ROLE_VENDOR_STAFF]

    def get(self, request):
        field = get_vendor_field(Product)
        try:
            products = Product.objects.filter(**{field: request.user}).prefetch_related(
                'order_items'
            )
        except Exception:
            logger.warning("Product model missing vendor field '%s'", field)
            products = Product.objects.none()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


class DriverDeliveriesAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [ROLE_DRIVER]

    def get(self, request):
        Delivery = apps.get_model('orders', 'Delivery')
        if not Delivery or DeliverySerializer is None:
            return Response([])
        deliveries = Delivery.objects.filter(driver=request.user)
        serializer = DeliverySerializer(deliveries, many=True)
        return Response(serializer.data)

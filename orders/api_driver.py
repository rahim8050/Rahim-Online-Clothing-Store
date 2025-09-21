from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import decorators, permissions, response, status, viewsets

from .models import Delivery
from .serializers import DeliverySerializer, DriverDeliveryListSerializer


class IsDriver(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return u and u.is_authenticated and u.groups.filter(name__iexact="driver").exists()


class DeliveryViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, IsDriver]
    serializer_class = DeliverySerializer

    def get_queryset(self):
        return Delivery.objects.filter(driver=self.request.user).select_related("order")

    def list(self, request):
        qs = self.get_queryset().order_by("-updated_at")
        ser = DriverDeliveryListSerializer(qs, many=True)
        return response.Response(ser.data)

    def retrieve(self, request, pk=None):
        d = get_object_or_404(self.get_queryset(), pk=pk)
        return response.Response(DeliverySerializer(d).data)

    def _owned_locked(self, request, pk) -> Delivery:
        with transaction.atomic():
            d = get_object_or_404(Delivery.objects.select_for_update(), pk=pk, driver=request.user)
            return d

    @decorators.action(detail=True, methods=["post"])  # /deliveries/:id/pickup/
    def pickup(self, request, pk=None):
        d = self._owned_locked(request, pk)
        try:
            d.mark_picked_up(by=request.user, when=self._parse_when(request))
            d.save(update_fields=["status", "picked_up_at", "updated_at"])
        except ValueError as e:
            return response.Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(DeliverySerializer(d).data)

    @decorators.action(detail=True, methods=["post"])  # /deliveries/:id/enroute/
    def enroute(self, request, pk=None):
        d = self._owned_locked(request, pk)
        try:
            d.mark_en_route(by=request.user, when=self._parse_when(request))
            d.save(update_fields=["status", "picked_up_at", "updated_at"])
        except ValueError as e:
            return response.Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(DeliverySerializer(d).data)

    @decorators.action(detail=True, methods=["post"])  # /deliveries/:id/deliver/
    def deliver(self, request, pk=None):
        d = self._owned_locked(request, pk)
        try:
            d.mark_delivered(by=request.user, when=self._parse_when(request))
            d.save(update_fields=["status", "picked_up_at", "delivered_at", "updated_at"])
        except ValueError as e:
            return response.Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return response.Response(DeliverySerializer(d).data)

    def _parse_when(self, request):
        w = request.data.get("when")
        if not w:
            return timezone.now()
        try:
            # DRF will parse ISO-8601 automatically; but accept raw string here
            return timezone.datetime.fromisoformat(str(w))
        except Exception:
            return timezone.now()

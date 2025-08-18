"""Vendor staff management endpoints.

Example requests:
- GET /apis/vendor/staff/?owner_id=1
- POST /apis/vendor/staff/invite/ { "staff_id": 42, "owner_id": 1 }
- PATCH /apis/vendor/staff/toggle/ { "staff_id": 42, "is_active": false, "owner_id": 1 }
- DELETE /apis/vendor/staff/42/?owner_id=1

All endpoints require Authorization: Bearer <JWT>.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

try:
    from drf_spectacular.utils import extend_schema
except Exception:  # pragma: no cover

    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


from .models import VendorStaff
from .serializers_vendor_staff import (
    VendorStaffInviteSerializer,
    VendorStaffReadSerializer,
    VendorStaffRemoveSerializer,
    VendorStaffToggleSerializer,
)
from .utils import resolve_vendor_owner_for


class VendorStaffListAPI(APIView):
    """List vendor staff memberships for an owner."""

    permission_classes = [IsAuthenticated]  # TODO: restrict to vendor group

    @extend_schema(tags=["Vendor Staff"], summary="List vendor staff")
    def get(self, request):
        owner_param = request.query_params.get("owner_id")
        try:
            owner_id = resolve_vendor_owner_for(
                request.user, int(owner_param) if owner_param is not None else None
            )
        except ValueError as e:
            return Response({"owner_id": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        qs = (
            VendorStaff.objects.filter(owner_id=owner_id)
            .select_related("staff", "owner")
            .order_by("-is_active", "-id")
        )
        ser = VendorStaffReadSerializer(qs, many=True)
        return Response(ser.data)


class VendorStaffInviteAPI(APIView):
    """Invite a user to become vendor staff."""

    permission_classes = [IsAuthenticated]  # TODO: restrict to vendor group

    @extend_schema(tags=["Vendor Staff"], summary="Invite staff")
    def post(self, request):
        ser = VendorStaffInviteSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)
        membership = ser.save()
        out_ser = VendorStaffReadSerializer(membership)
        return Response(out_ser.data, status=status.HTTP_201_CREATED)


class VendorStaffRemoveAPI(APIView):
    """Remove a vendor staff membership (idempotent)."""

    permission_classes = [IsAuthenticated]  # TODO: restrict to vendor group

    @extend_schema(tags=["Vendor Staff"], summary="Remove staff")
    def post(self, request):
        ser = VendorStaffRemoveSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)
        data = ser.save()
        return Response(data)

    @extend_schema(tags=["Vendor Staff"], summary="Remove staff")
    def delete(self, request, staff_id: int):
        payload = {
            "staff_id": staff_id,
            "owner_id": request.query_params.get("owner_id"),
        }
        ser = VendorStaffRemoveSerializer(data=payload, context={"request": request})
        ser.is_valid(raise_exception=True)
        data = ser.save()
        return Response(data)


class VendorStaffToggleActiveAPI(APIView):
    """Toggle active status for a vendor staff membership."""

    permission_classes = [IsAuthenticated]  # TODO: restrict to vendor group

    @extend_schema(tags=["Vendor Staff"], summary="Toggle staff active state")
    def patch(self, request):
        ser = VendorStaffToggleSerializer(
            data=request.data, context={"request": request}
        )
        ser.is_valid(raise_exception=True)
        membership = ser.save()
        out_ser = VendorStaffReadSerializer(membership)
        return Response(out_ser.data)

import logging

from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.services.vendor_staff import (
    invite_vendor_staff,
    accept_vendor_staff_invite,
)

logger = logging.getLogger(__name__)


class IsVendorOwner(BasePermission):
    """Allow access only to users in the Vendor group."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.groups.filter(name="Vendor").exists()
        )


class VendorStaffInviteAPI(APIView):
    permission_classes = [IsAuthenticated, IsVendorOwner]

    class InputSerializer(serializers.Serializer):
        owner_id = serializers.IntegerField(required=False)
        staff_id = serializers.IntegerField()

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        owner_id = serializer.validated_data.get("owner_id") or request.user.id
        staff_id = serializer.validated_data["staff_id"]
        resend = request.query_params.get("resend") == "1"

        User = get_user_model()
        try:
            staff = User.objects.get(id=staff_id)
        except User.DoesNotExist:
            return Response({"detail": "staff not found"}, status=status.HTTP_404_NOT_FOUND)

        if not staff.email:
            return Response({"detail": "staff email required"}, status=status.HTTP_400_BAD_REQUEST)

        service_result = invite_vendor_staff(request, owner_id, staff, resend)

        status_code = (
            status.HTTP_201_CREATED
            if service_result.get("created") and service_result.get("emailed")
            else status.HTTP_200_OK
        )
        logger.info(
            "Vendor staff invite",
            extra={"owner": owner_id, "staff": staff.id, "result": service_result},
        )
        return Response(service_result, status=status_code)


class VendorStaffAcceptAPI(APIView):
    permission_classes = [IsAuthenticated]  # AllowAny if token-based access only

    def post(self, request, token: str):
        service_result = accept_vendor_staff_invite(token, user_id=request.user.id)
        status_code = service_result.get("code", status.HTTP_200_OK)

        log_extra = {"token": token, "user": request.user.id, "result": service_result}
        if status_code >= 400:
            logger.error("Vendor staff accept failed", extra=log_extra)
        else:
            logger.info("Vendor staff accept", extra=log_extra)

        return Response(service_result, status=status_code)

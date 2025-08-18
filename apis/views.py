# apis/views.py
from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.urls import reverse
from django.apps import apps
import logging
from django.conf import settings
# apis/views.py (top)
from users.utils import resolve_vendor_owner_for




from django.core.mail import EmailMultiAlternatives
from django.core.signing import TimestampSigner, dumps as sign, BadSignature, SignatureExpired
from django.db import transaction


from .serializers import VendorStaffInviteSerializer
from users.models import VendorStaff
from django.core.signing import loads as unsign

signer = TimestampSigner()

from rest_framework import status
from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.contrib.sites.shortcuts import get_current_site
from core.permissions import InGroups
from product_app.queries import shopable_products_q
from product_app.models import Product
from product_app.utils import get_vendor_field
from orders.models import Delivery, OrderItem
from users.constants import VENDOR, VENDOR_STAFF, DRIVER
from users.models import VendorStaff  # <-- FIX: was missing
from rest_framework import permissions
from users.permissions import IsVendorOrVendorStaff, IsDriver

# If your vendor staff serializers live in apis.serializers, keep this.
# If you followed the earlier split, switch to: from users.serializers_vendor_staff import ...
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

logger = logging.getLogger(__name__)
User = get_user_model()



class WhoAmI(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request):
        return Response({"id": request.user.id, "email": getattr(request.user, "email", None)})

def orderitem_reverse_name() -> str:
    rel_name = OrderItem._meta.get_field("product").remote_field.related_name
    if rel_name == "+":
        return ""
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
            qs = qs.filter(shopable_products_q(u))
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        return qs

class VendorProductsAPI(APIView):
    """
    Returns products for the vendor owner context of the caller.
    - Vendor owner: sees their own products
    - Vendor staff: sees the selected owner's products (owner_id query param) or
      auto-resolved if they have exactly one allowed owner
    """
    permission_classes = [IsAuthenticated, IsVendorOrVendorStaff]
    required_groups = [VENDOR, VENDOR_STAFF]

    def get(self, request):
        # 1) Resolve owner context (owner_id may be omitted if user has exactly one)
        raw_owner = request.query_params.get("owner_id", None)
        try:
            owner_id = resolve_vendor_owner_for(
                request.user,
                raw_owner,
                require_explicit_if_multiple=True,  # set False to auto-pick first if you prefer
            )
        except ValueError as e:
            # Ambiguous or malformed owner_id -> 400 with clear message
            return Response({"owner_id": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        # PermissionDenied will bubble to 403 automatically (good)

        # 2) Filter products by the vendor field
        field = get_vendor_field(Product)            # e.g. "vendor" or "owner"
        vendor_field_id = f"{field}_id"              # FK filter by id without fetching the User

        try:
            base_qs = Product.objects.filter(**{vendor_field_id: owner_id})
        except Exception:
            logger.warning("Product model missing vendor field '%s'", field, exc_info=True)
            base_qs = Product.objects.none()

        # 3) Optional text search
        q = request.query_params.get("q")
        if q:
            base_qs = base_qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        # 4) Prefetch order items efficiently (works regardless of related_name)
        rev = orderitem_reverse_name()
        if rev:
            oi_qs = (OrderItem.objects
                     .select_related("order", "product")
                     .only("id", "order_id", "product_id", "price", "quantity", "delivery_status"))
            products = base_qs.prefetch_related(Prefetch(rev, queryset=oi_qs))
        else:
            products = base_qs

        serializer = ProductSerializer(products, many=True, context={"request": request})
        return Response(serializer.data)



class DriverDeliveriesAPI(APIView):
    permission_classes = [IsAuthenticated, IsDriver]
    required_groups = [DRIVER]

    def get(self, request):
        qs = Delivery.objects.filter(driver=request.user).select_related("order").order_by("-id")
        serializer = DeliverySerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


class DeliveryAssignAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [VENDOR, VENDOR_STAFF]

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
    required_groups = [VENDOR, VENDOR_STAFF]

    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk)
        delivery.driver = None
        delivery.status = Delivery.Status.PENDING
        delivery.assigned_at = None
        delivery.save(update_fields=["driver", "status", "assigned_at"])
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DeliveryAcceptAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [DRIVER]

    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, driver__isnull=True)
        delivery.mark_assigned(request.user)
        delivery.save(update_fields=["driver", "status", "assigned_at"])
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DeliveryStatusAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [DRIVER]

    def post(self, request, pk):
        delivery = get_object_or_404(Delivery, pk=pk, driver=request.user)
        ser = DeliveryStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_status = ser.validated_data["status"]  # <-- FIX: avoid shadowing rest_framework.status
        delivery.status = new_status
        if new_status == Delivery.Status.PICKED_UP:
            delivery.picked_up_at = timezone.now()
        if new_status == Delivery.Status.DELIVERED:
            delivery.delivered_at = timezone.now()
        delivery.save(update_fields=["status", "picked_up_at", "delivered_at"])
        return Response(DeliverySerializer(delivery, context={"request": request}).data)


class DriverLocationAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [DRIVER]

    def post(self, request):
        lat = request.data.get("lat")
        lng = request.data.get("lng")
        logger.info("Driver %s location lat=%s lng=%s", request.user.pk, lat, lng)
        return Response({"ok": True})


class VendorProductCreateAPI(CreateAPIView):
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
                kwargs={"id": product.id, "slug": product.slug}
            )
        }
        return Response(out_ser.data, status=status.HTTP_201_CREATED, headers=headers)






class IsVendorOwner(permissions.BasePermission):
    """
    Example permission: only users allowed to act as vendor owners may invite.
    Adjust logic to your RBAC/groups (e.g., user.groups.filter(name="Vendor").exists()).
    """
    message = "Only vendor owners can invite staff."
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.groups.filter(name="Vendor").exists()

class VendorStaffInviteAPI(APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendorOwner]

    def post(self, request):
        ser = VendorStaffInviteSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)

        owner_id = ser.validated_data["owner_id"]
        staff = ser.validated_data["staff"]

        # Ensure you have a DB-level unique constraint on (owner, staff)
        # e.g. class Meta: constraints = [models.UniqueConstraint(fields=["owner","staff"], name="uniq_owner_staff")]
        with transaction.atomic():
            vs, created = VendorStaff.objects.select_for_update().get_or_create(
                owner_id=owner_id,
                staff=staff,
                defaults={"status": "pending", "is_active": False},
            )

            # Already active → conflict
            if vs.is_active:
                return Response(
                    {"detail": "Staff is already active for this owner."},
                    status=status.HTTP_409_CONFLICT,
                )

            # Normalize any stale state back to "pending"
            if not created and vs.status != "pending":
                vs.status = "pending"
                vs.is_active = False
                vs.save(update_fields=["status", "is_active"])

            # Build a signed, expiring token so the invite link isn't a raw ID
            payload = {"vs_id": vs.id, "staff_id": staff.id}
            token = sign(payload)  # default salt+signer; can pass salt="vendor-staff"
            # e.g. path("vendor/staff/accept/<str:token>/", AcceptInviteAPI.as_view(), name="vendor-staff-accept")
            path = reverse("vendor-staff-accept", args=[token])

            # Prefer absolute URI so emails work off any domain/proxy
            invite_link = request.build_absolute_uri(path)

            if created:
                subject = f"You're invited to join {get_current_site(request).domain}"
                html_content = render_to_string(
                    "emails/vendor_staff_invite.html",
                    {
                        "staff": staff,
                        "owner": request.user,
                        "invite_link": invite_link,
                        "site_name": get_current_site(request).domain,
                    },
                )
                text_content = (
                    "You've been invited as vendor staff.\n\n"
                    f"Accept your invite: {invite_link}"
                )

                # Send only after commit so we don't email on a rolled-back txn
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
                        logger.info("Invite email sent to %s (vs=%s)", staff.email, vs.id)
                    except Exception as e:
                        logger.exception("Invite email failed for vs=%s: %s", vs.id, e)

                transaction.on_commit(_send)

        return Response(
            {
                "ok": True,
                "message": "Invite created and email queued." if created else "Invite already pending.",
                "data": {
                    "vendor_staff_id": vs.id,
                    "owner_id": vs.owner_id,
                    "staff_id": vs.staff_id,
                    "status": vs.status,
                    "is_active": vs.is_active,
                    "invite_link_preview": invite_link if created else None,  # helpful for Postman/manual testing
                },
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )




class VendorStaffAcceptAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]  # or AllowAny if you will log in later

    TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

    def post(self, request, token: str):
        try:
            payload = unsign(token, max_age=self.TOKEN_MAX_AGE)
        except SignatureExpired:
            return Response({"detail": "Invite link expired."}, status=410)
        except BadSignature:
            return Response({"detail": "Invalid invite link."}, status=400)

        vs_id = payload.get("vs_id")
        staff_id = payload.get("staff_id")

        with transaction.atomic():
            vs = VendorStaff.objects.select_for_update().get(pk=vs_id, staff_id=staff_id)
            if vs.is_active:
                return Response({"detail": "Already accepted."}, status=200)
            vs.status = "accepted"
            vs.is_active = True
            vs.save(update_fields=["status", "is_active"])

        return Response({"ok": True, "message": "Invite accepted."}, status=200)


class VendorStaffRemoveAPI(APIView):
    permission_classes = [IsAuthenticated, InGroups]
    required_groups = [VENDOR, VENDOR_STAFF]

    def post(self, request):
        ser = VendorStaffRemoveSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        data = ser.save()
        return Response(data)


class VendorApplyAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if apps.get_model("users", "VendorApplication").objects.filter(
            user=request.user, status="pending"
        ).exists():
            return Response({"detail": "You already have a pending application."},
                            status=status.HTTP_400_BAD_REQUEST)
        ser = VendorApplySerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        app = ser.save()
        return Response({"ok": True, "application_id": app.id})

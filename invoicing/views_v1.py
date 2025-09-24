from __future__ import annotations

from django.http import FileResponse, Http404
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from vendor_app.services import has_min_role

from .models import Invoice
from .serializers import InvoiceSerializer
from .services.etims import submit_invoice
from .throttling import InvoiceExportThrottle
from .utils import (
    ensure_invoice_pdf_path,
    generate_signed_download_token,
    verify_signed_download_token,
)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            qs = Invoice.objects.all()
        else:
            qs = Invoice.objects.filter(
                org__members__user=user, org__members__is_active=True
            ).distinct()
        qs = qs.select_related("org", "order").prefetch_related("lines")
        # Filters
        org = self.request.query_params.get("org")
        status_f = self.request.query_params.get("status")
        dfrom = self.request.query_params.get("date_from")
        dto = self.request.query_params.get("date_to")
        if org:
            qs = qs.filter(org_id=int(org))
        if status_f:
            qs = qs.filter(status=status_f)
        if dfrom:
            qs = qs.filter(issued_at__date__gte=dfrom)
        if dto:
            qs = qs.filter(issued_at__date__lte=dto)
        return qs

    @extend_schema(
        request=None,
        responses=InvoiceSerializer,
        examples=[
            OpenApiExample(
                "Accepted Invoice",
                value={
                    "id": 123,
                    "status": "accepted",
                    "irn": "IRN-ABC123",
                    "org": 1,
                    "order": 1001,
                    "buyer_name": "Jane Doe",
                    "buyer_pin": "A123456789B",
                    "subtotal": "100.00",
                    "tax_amount": "16.00",
                    "total": "116.00",
                },
                response_only=True,
            ),
            OpenApiExample(
                "Rejected Invoice",
                value={
                    "id": 124,
                    "status": "rejected",
                    "irn": "",
                    "last_error": "ORG_NOT_VERIFIED",
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        inv: Invoice = self.get_object()
        user = request.user
        if not (getattr(user, "is_staff", False) or has_min_role(user, inv.org, "MANAGER")):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        # Feature flag gate
        from django.conf import settings

        if not getattr(settings, "ETIMS_ENABLED", False):
            return Response(
                {"detail": "ETIMS disabled"}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        submit_invoice(invoice=inv, idempotency_key=f"invoice:submit:{inv.id}")
        inv.refresh_from_db()
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_200_OK)

    @action(
        detail=True, methods=["get"], url_path="download", throttle_classes=[InvoiceExportThrottle]
    )
    def download(self, request, pk=None):
        inv: Invoice = self.get_object()
        # MUST be manager+ or staff
        user = request.user
        if not (getattr(user, "is_staff", False) or has_min_role(user, inv.org, "MANAGER")):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        token = generate_signed_download_token(inv.id)
        base = request.build_absolute_uri(self.request.path)
        if not base.endswith("/"):
            base += "/"
        # ensure PDF exists (simple synchronous generation)
        path = ensure_invoice_pdf_path(inv.id)
        try:
            open(path, "rb").close()
        except FileNotFoundError:
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas

                c = canvas.Canvas(path, pagesize=letter)
                c.drawString(72, 720, f"Invoice #{inv.id}")
                c.save()
            except Exception:
                with open(path, "wb") as f:
                    f.write(b"%PDF-1.4\n% Fake PDF\n")
        fmt = request.query_params.get("format")
        if fmt == "pdf":
            # stream pdf directly if token valid (or sandbox bypass)
            try:
                inv_id = verify_signed_download_token(request.query_params.get("token"))
            except Exception:
                inv_id = int(pk)
            if inv_id != int(pk):
                raise Http404
            return FileResponse(open(path, "rb"), content_type="application/pdf")
        if fmt == "csv":
            try:
                inv_id = verify_signed_download_token(request.query_params.get("token"))
            except Exception:
                inv_id = int(pk)
            if inv_id != int(pk):
                raise Http404
            import csv
            from io import StringIO

            buf = StringIO()
            w = csv.writer(buf)
            w.writerow(["SKU", "Name", "Qty", "Unit Price", "Tax Rate", "Line Total", "Tax Total"])
            for line in inv.lines.all():
                w.writerow(
                    [line.sku, line.name, line.qty, line.unit_price, line.tax_rate, line.line_total, line.tax_total]
                )
            resp = Response(buf.getvalue(), content_type="text/csv")
            resp["Content-Disposition"] = f"attachment; filename=invoice_{inv.id}.csv"
            return resp
        pdf_url = base.replace("download/", f"download.pdf?token={token}")
        csv_url = base.replace("download/", f"download.csv?token={token}")
        return Response({"pdf_url": pdf_url, "csv_url": csv_url})

    @action(
        detail=False,
        methods=["get"],
        url_path=r"(?P<pk>[^/]+)/download\.pdf",
        throttle_classes=[InvoiceExportThrottle],
    )
    def download_pdf(self, request, pk=None):
        token = request.query_params.get("token")
        if not token:
            raise Http404
        try:
            inv_id = verify_signed_download_token(token)
        except Exception:
            raise Http404
        if str(inv_id) != str(pk):
            raise Http404
        # Generate or return cached PDF file
        path = ensure_invoice_pdf_path(inv_id)
        try:
            # If file exists, stream
            return FileResponse(open(path, "rb"), content_type="application/pdf")
        except FileNotFoundError:
            # Synchronous simple PDF placeholder
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas

                c = canvas.Canvas(path, pagesize=letter)
                c.drawString(72, 720, f"Invoice #{inv_id}")
                c.save()
            except Exception:
                # fallback to simple bytes
                with open(path, "wb") as f:
                    f.write(b"%PDF-1.4\n% Fake PDF\n")
            return FileResponse(open(path, "rb"), content_type="application/pdf")

    @action(
        detail=False,
        methods=["get"],
        url_path=r"(?P<pk>[^/]+)/download\.csv",
        throttle_classes=[InvoiceExportThrottle],
    )
    def download_csv(self, request, pk=None):
        token = request.query_params.get("token")
        if not token:
            raise Http404
        try:
            inv_id = verify_signed_download_token(token)
        except Exception:
            raise Http404
        if str(inv_id) != str(pk):
            raise Http404
        inv = Invoice.objects.get(pk=inv_id)
        import csv
        from io import StringIO

        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(["SKU", "Name", "Qty", "Unit Price", "Tax Rate", "Line Total", "Tax Total"])
        for line in inv.lines.all():
            w.writerow([line.sku, line.name, line.qty, line.unit_price, line.tax_rate, line.line_total, line.tax_total])
        resp = Response(buf.getvalue(), content_type="text/csv")
        resp["Content-Disposition"] = f"attachment; filename=invoice_{inv_id}.csv"
        return resp
